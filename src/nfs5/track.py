"""Track models: GameData/Track/<name>.crp ("Trak" container) + <name>.fsh.

Same container as cars (see crp.py). Track geometry has no normals; each
triangle corner carries a "df" colour (pre-baked lighting) stored as BGRA
like a Direct3D D3DCOLOR (RGBA order made snow pink); 0x80 looks like neutral
brightness, so colours are applied as modulate-2x. Materials ("mt",
76 bytes) name their texture directly: bytes 38..39 hold the tag "ns"
(reversed "sn", the misc part naming <track>.fsh) and bytes 40..43 the
4-character SHPI entry name. Material class at bytes 16..31: "Normal",
"Opaque", "FakeSort", "NormMatState", "FullAmbient", ... Alpha handling is a
hypothesis: FakeSort blends, any other material alpha-tests when its texture
has transparent texels.
Objects placed in the world carry a "tr" matrix like car parts.

Road ("SimD", 80-byte nodes, roughly every 6 m): u32 flags, f32 position[3],
up[3], forward[3], right[3], 3 zero floats, 4 widths (lane/verge extents in
metres; exact split is a hypothesis). "SimT" holds u32 node counts of the
consecutive chains (main road first, then branches).
"""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import crp, fsh

FLIP = np.array([1, 1, -1], np.float32)


def alpha_mode(kind, rgba):
    if kind == "FakeSort":
        return "BLEND"
    return "MASK" if (rgba[..., 3] < 128).mean() > 0.01 else "OPAQUE"


@dataclass
class TrackMaterial:
    index: int
    kind: str
    texture: str
    flags: int


class Track:
    def __init__(self, track_dir, name):
        track_dir = Path(track_dir)
        self.name = name
        self.crp = crp.load(track_dir / f"{name}.crp")
        self.archive = fsh.load(track_dir / f"{name}.fsh")
        self.images = {}
        for e in self.archive.entries:
            self.images.setdefault(e.name, e)
        self.materials = {}
        for p in self.crp.misc:
            if p.tag == "mt":
                d = p.data
                self.materials[p.index] = TrackMaterial(
                    p.index, d[16:32].split(b"\0", 1)[0].decode("latin-1"),
                    d[40:44].decode("latin-1"), int.from_bytes(d[44:48], "little"))

    def road(self):
        """Road chains as lists of node dicts, in the right-handed output frame."""
        sd = next(p for p in self.crp.misc if p.tag == "SimD")
        st = next(p for p in self.crp.misc if p.tag == "SimT")
        f = np.frombuffer(sd.data, "<f4").reshape(sd.count, 20)
        flags = np.frombuffer(sd.data, "<u4").reshape(sd.count, 20)[:, 0]
        sizes = [int(x) for x in np.frombuffer(st.data, "<u4") if x]
        chains, start = [], 0
        for n in sizes:
            rows = range(start, min(start + n, sd.count))
            chains.append([{"p": (f[i, 1:4] * FLIP).round(3).tolist(),
                            "up": (f[i, 4:7] * FLIP).round(4).tolist(),
                            "fwd": (f[i, 7:10] * FLIP).round(4).tolist(),
                            "right": (f[i, 10:13] * FLIP).round(4).tolist(),
                            "widths": f[i, 16:20].round(3).tolist(),
                            "flags": int(flags[i])} for i in rows])
            start += n
        return chains

    def meshes(self, lod=0):
        for art in self.crp.articles:
            m = crp.article_mesh(art, lod)
            if m is not None:
                yield art.name.strip(), m

    def batches(self, lod=0):
        """Triangles grouped by texture, in the right-handed output frame."""
        groups = {}
        for _name, m in self.meshes(lod):
            for mat, first, count in m["draws"]:
                tm = self.materials.get(mat)
                key = (tm.texture, tm.kind) if tm else ("", "Opaque")
                sl = slice(first, first + count)
                g = groups.setdefault(key, {"p": [], "t": [], "c": []})
                g["p"].append(m["positions"][sl] * FLIP)
                g["t"].append(m["uvs"][sl])
                g["c"].append(m["colors"][sl])
        out = []
        for (tex, kind), g in sorted(groups.items()):
            img = self.images.get(tex)
            rgba = fsh.entry_rgba(img) if img else np.full((4, 4, 4), 255, np.uint8)
            colors = np.concatenate(g["c"])[:, [2, 1, 0, 3]].astype(np.float32)  # BGRA -> RGBA
            colors[:, :3] = np.minimum(colors[:, :3] / 128.0, 1.0)  # Модуляция ×2 с ограничением диапазона.
            colors[:, 3] = colors[:, 3] / 255.0
            out.append({"name": f"{tex}:{kind}", "texture": tex, "kind": kind,
                        "p": np.concatenate(g["p"]), "t": np.concatenate(g["t"]),
                        "c": colors, "rgba": rgba, "mode": alpha_mode(kind, rgba),
                        "unlit": True})
        return out


def main(argv):
    from . import export
    track_dir, out = Path(argv[1]), Path(argv[2])
    names = argv[3:] or sorted(p.stem for p in track_dir.glob("*.crp"))
    out.mkdir(parents=True, exist_ok=True)
    for name in names:
        t = Track(track_dir, name)
        b = t.batches()
        tris = export.write_glb_batches(out / f"{name}.glb", name, b, repeat=True)
        road = t.road()
        (out / f"{name}.road.json").write_text(json.dumps({"chains": road}, separators=(",", ":")))
        print(f"{name}: {tris} triangles, {len(b)} texture batches, "
              f"road chains {[len(c) for c in road]}", flush=True)


if __name__ == "__main__":
    import sys
    main(sys.argv)
