"""Assemble a drivable-looking car model from CarModel/<name>.{crp,tpg,clr}.

Texture pages (tpg "tpageN") are atlases built from the CRP-embedded SHPI
archives ("sf" parts, indexed by tpg file number - 1) or, for files marked
"global=K", from the shared GameData/CarModel/*.fsh archives. Each image is
pasted at its SHPI position. A page with "sourcetpage" serves the mirrored
half of the car: both halves share UVs, so every image is flipped
horizontally in place (not the whole atlas).

Paint: exterior pages are near-white; the hypothesis implemented here is that
texels with alpha < 255 take the .clr colour1 multiplied in (lights and badges
have alpha 255). This is an approximation, not confirmed renderer behaviour.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import crp, fsh, ini

GLOBAL_FILES = {1: "Shadow.fsh", 2: "INTGLASS.FSH", 3: "Suit.fsh", 4: "Head.fsh", 5: "Cabrio.fsh"}

# Детали, не входящие во внешний вид закрытого купе по умолчанию.
HIDDEN_PREFIXES = ("Cabrio", "Driver", "Legs", "LeftArm", "RightArm", "LeftHand",
                   "RightHand", "LOD", "Glare", "DecalHood", "DecalDoor", "DecalTrunk")


@dataclass
class Page:
    index: int            # Номер текстурной страницы, начиная с нуля.
    rgba: np.ndarray
    mode: str             # OPAQUE | MASK | BLEND
    painted: bool


def _compose(archive, width, height, prefer=None, mirror=False):
    page = np.zeros((height, width, 4), np.uint8)
    # Несколько картинок могут занимать один прямоугольник: варианты колёс или крыши.
    # Рисуем поздние первыми, чтобы первая или предпочтительная картинка оказалась сверху.
    entries = list(archive.entries)
    if prefer:
        entries.sort(key=lambda e: e.name.strip() not in prefer)
    for e in reversed(entries):
        x, y = e.position
        img = fsh.entry_rgba(e)
        if mirror:
            img = img[:, ::-1]
        h, w = min(e.height, height - y), min(e.width, width - x)
        if h > 0 and w > 0:
            page[y:y + h, x:x + w] = img[:h, :w]
    return page


def overlapping_variants(meshes, grid=0.01, share=0.3):
    """Alternative versions of a part (Interior/Interior1/..., Roof/Roof1) occupy
    the same place; drawing all of them makes the surfaces flicker. The game picks
    one per body style through code that is not restored yet, so here: within a
    name group (trailing digits and a/b stripped) keep the base part and drop a
    variant when more than `share` of its triangle centres (1 cm grid) coincide
    with a part already kept. A stand-in, not the game's rule."""
    import collections
    import re
    cells = {}
    for name, m in meshes:
        p = m["positions"].astype(np.float64).reshape(-1, 3, 3)
        cen = (p[:, 0] + p[:, 1] + p[:, 2]) / 3.0
        cells.setdefault(name, set()).update(map(tuple, np.floor(cen / grid).astype(np.int64)))
    groups = collections.defaultdict(list)
    for n in cells:
        groups[re.sub(r"[0-9]*[ab]?$", "", n)].append(n)
    drop = set()
    for names in groups.values():
        kept = []
        for n in sorted(names, key=lambda x: (len(x), x)):
            if any(len(cells[n] & cells[k]) > share * len(cells[n]) for k in kept):
                drop.add(n)
            else:
                kept.append(n)
    return drop


def hsv_to_rgb(h, s, v):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h / 255.0, s / 255.0, v / 255.0)
    return np.array([r, g, b])


class CarModel:
    def __init__(self, car_dir, name, colour=1):
        car_dir = Path(car_dir)
        self.name = name
        self.crp = crp.load(car_dir / f"{name}.crp")
        self.tpg = ini.load(car_dir / f"{name}.tpg")
        clr_path = car_dir / f"{name}.clr"
        self.clr = ini.load(clr_path) if clr_path.exists() else {}
        sect = self.clr.get(f"section{colour}", {})
        if "color1.r" in sect:
            self.paint = np.array([int(sect[f"color1.{c}"]) for c in "rgb"]) / 255.0
        else:
            self.paint = np.array([0.8, 0.8, 0.8])
        self.car_dir = car_dir
        self.pages = self._build_pages()

    def _build_pages(self):
        hdr = self.tpg.get("header", {})
        ntp = int(hdr.get("numtpages", 0))
        nfiles = int(hdr.get("numfiles", 0))
        embedded = self.crp.textures()
        file_of_tpage = {}
        for f in range(1, nfiles + 1):
            det = self.tpg.get(f"file{f}.details", {})
            if "tpage" in det:
                file_of_tpage[int(det["tpage"])] = (f, det)
        pages = {}
        archives = {}
        for t in range(1, ntp + 1):
            det = self.tpg.get(f"tpage{t}.details", {})
            w, h = int(det.get("width", 256)), int(det.get("height", 256))
            mirror = "sourcetpage" in det
            src_t = int(det["sourcetpage"]) if mirror else t
            f, fdet = file_of_tpage.get(src_t, (None, {}))
            archive = archives.get(src_t)
            if archive is None and f is not None and (f - 1) in embedded:
                archive = embedded[f - 1]
            elif archive is None and "global" in fdet:
                p = self.car_dir / GLOBAL_FILES.get(int(fdet["global"]), "")
                if p.is_file():
                    archive = fsh.load(p)
            archives[src_t] = archive
            if archive is None:
                rgba = np.full((h, w, 4), 255, np.uint8)
            else:
                rgba = _compose(archive, w, h, prefer=("whg", "top"), mirror=mirror)
            fname = self.tpg["header"].get(f"file{f}", "") if f else ""
            painted = fname in ("exterior.fsh",)
            if painted:
                rgba = self._paint(rgba)
            if det.get("window") == "1" or fname in ("glass.fsh", "intglass.fsh", "shadow.fsh"):
                mode = "BLEND"
            elif painted:
                mode = "OPAQUE"
            else:
                mode = "MASK"
            pages[t - 1] = Page(t - 1, rgba, mode, painted)
        return pages

    def _paint(self, rgba):
        out = rgba.astype(np.float32)
        mask = rgba[..., 3] < 255
        out[mask, :3] *= self.paint
        out[..., 3] = 255
        return out.clip(0, 255).astype(np.uint8)

    def material_page(self):
        return {m.index: int.from_bytes(m.raw[40:44], "little") for m in self.crp.materials()}

    def meshes(self, lod=1, include_hidden=False):
        """Yield (article_name, mesh dict) for the visible articles."""
        out = []
        for art in self.crp.articles:
            if not include_hidden and art.name.strip().startswith(HIDDEN_PREFIXES):
                continue
            m = crp.article_mesh(art, lod)
            if m is not None:
                out.append((art.name.strip(), m))
        drop = set() if include_hidden else overlapping_variants(out)
        return [(n, m) for n, m in out if n not in drop]
