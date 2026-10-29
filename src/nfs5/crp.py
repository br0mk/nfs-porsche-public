"""NFS: Porsche Unleashed CRP car/track model container.

All multi-byte values are little-endian. Four-character tags are stored
byte-reversed ("Car " is stored as " raC"); this module exposes them in reading
order. Every 16-byte directory entry stores its payload offset relative to the
entry itself.

File header (16 bytes):
    tag "Car ", u32 info = (article_count << 5) | flags, u32 misc_count, u32 ?
Then <article_count> article entries and <misc_count> misc entries.

Article entry: tag "Arti", u32 info, u32 part_count, u32 offset in 16-byte
units (relative to the entry). The parts are 16-byte part entries:
    u16 index, 2-char tag, u32 info (low byte flags, length = info >> 8),
    u32 item count, u32 byte offset (relative to the part entry).
Misc entries use the same part-entry layout (4-char tags have no index).

Observed part tags inside an article:
    "Base" transform/bounds, "Name" C string, "vt" vertices (4 x f32),
    "nm" normals (4 x f32), "uv" texture coordinates (2 x f32),
    "pr" primitive (one material, indexed triangle list), "$n" per-triangle
    16-byte records referenced from "pr".
Part index: low nibble = LOD group (1 = high detail), high nibble of "vt"/"nm"
= deformation state (0 = undamaged); for "pr" the high byte is the LOD level.
"""
import struct
from dataclasses import dataclass, field

import numpy as np

from . import fsh, refpack


def _tag(raw: bytes) -> str:
    return raw[::-1].decode("latin-1")


@dataclass
class Part:
    index: int
    tag: str
    info: int
    count: int
    data: bytes

    @property
    def flags(self):
        return self.info & 0xFF


@dataclass
class Primitive:
    lod: int
    number: int
    flags: int
    material: int
    bounds: tuple            # Центр сферы xyz и радиус; предположение.
    streams: dict            # Вид потока → (смещение в байтах, длина в байтах, индекс части).
    vertex_indices: np.ndarray
    uv_indices: np.ndarray

    @property
    def triangle_count(self):
        return len(self.vertex_indices) // 3


@dataclass
class Article:
    info: int
    parts: list = field(default_factory=list)

    def find(self, tag, index=None):
        return [p for p in self.parts if p.tag == tag and (index is None or p.index == index)]

    @property
    def name(self):
        names = self.find("Name")
        return names[0].data.split(b"\0", 1)[0].decode("latin-1") if names else ""


# Виды потоков в блоке «pr» (u16 по смещению 10). Определены по трассам,
# где есть только вершины, UV и цвета; у машин диапазоны потоков
# вершин и нормалей совпадают.
STREAM_VERTEX = 0          # «vt», элементы по 16 байт.
STREAM_NORMAL = 1          # «nm», элементы по 16 байт.
STREAM_UV = 2              # «uv», элементы по 8 байт.
STREAM_COLOR = 3           # «df», по 4 байта на угол треугольника, последовательно.
STREAM_TRIANGLE_DATA = 0x246E  # Тег «$n», по 16 байт на треугольник.


def parse_primitive(part: Part) -> Primitive:
    """Decode a "pr" block.

    Layout: u32 flags, u32 material (bit 31 set), 4 x f32 bounds, 16 zero
    bytes, u32 stream count, u32 index-stream count, then stream records
    {u32 id, u32 byte offset, u16 byte length, u16 kind, u16 group, u16 ?}
    and index-stream records {u16 group, 2-char tag "Iv"/"Iu", u32 offset},
    followed by the u8 index data. With no index streams the triangles use
    the referenced range sequentially (blocks may carry only "Iu").
    """
    b = part.data
    flags, mat = struct.unpack_from("<II", b, 0)
    bounds = struct.unpack_from("<4f", b, 8)
    nstreams, nindex = struct.unpack_from("<II", b, 40)
    streams = {}
    p = 48
    for _ in range(nstreams):
        _sid, off, length, kind, group = struct.unpack_from("<IIHHH", b, p)
        streams[kind] = (off, length, group)
        p += 16
    idx_streams = {}
    for _ in range(nindex):
        _group, tag, off = struct.unpack_from("<H2sI", b, p)
        idx_streams[_tag(tag)] = off
        p += 8
    n = part.count
    data = b[p:]
    # Отсутствие потока индексов означает последовательное использование атрибута.
    seq = np.arange(n, dtype=np.uint8)
    vi = np.frombuffer(data, np.uint8, n, idx_streams["Iv"]) if "Iv" in idx_streams else seq
    ui = np.frombuffer(data, np.uint8, n, idx_streams["Iu"]) if "Iu" in idx_streams else seq
    return Primitive(part.index >> 12, part.index & 0xFFF, flags, mat & 0xFFFF, bounds,
                     streams, vi, ui)


@dataclass
class Material:
    index: int
    name: str
    texture_page: int
    raw: bytes


@dataclass
class Car:
    info: int
    articles: list
    misc: list

    def materials(self):
        out = []
        for p in self.misc:
            if p.tag == "mt":
                name = p.data[16:32].split(b"\0", 1)[0].decode("latin-1")
                tpage = struct.unpack_from("<i", p.data, 164)[0]
                out.append(Material(p.index, name, tpage, p.data))
        return out

    def textures(self):
        """Embedded SHPI archives keyed by their "sf" index."""
        return {p.index: fsh.parse(p.data) for p in self.misc if p.tag == "sf"}


def _part(d: bytes, pos: int) -> Part:
    idx, tag2, info, count, off = struct.unpack_from("<H2sIII", d, pos)
    tag4 = _tag(d[pos:pos + 4])
    if tag4.isalpha() and len(tag4.strip()) == 4:
        index, tag = 0, tag4
    else:
        index, tag = idx, _tag(tag2)
    length = info >> 8
    return Part(index, tag, info, count, d[pos + off:pos + off + length])


def parse(d: bytes) -> Car:
    tag, info, misc_count, _unk = struct.unpack_from("<4sIII", d, 0)
    if _tag(tag) not in ("Car ", "Trak"):
        raise ValueError(f"not a CRP model: {tag!r}")
    n_articles = info >> 5
    articles = []
    pos = 16
    for _ in range(n_articles):
        atag, ainfo, count, off = struct.unpack_from("<4sIII", d, pos)
        if _tag(atag) != "Arti":
            raise ValueError(f"expected Arti at {pos:#x}, got {atag!r}")
        base = pos + off * 16
        art = Article(ainfo, [_part(d, base + 16 * k) for k in range(count)])
        articles.append(art)
        pos += 16
    misc = [_part(d, pos + 16 * k) for k in range(misc_count)]
    return Car(info, articles, misc)


def load(path) -> Car:
    return parse(refpack.load(path))


# Тип примитива — младший байт флагов «pr». 3 — список треугольников: вся геометрия
# машин и около 99 % геометрии трасс. Типы 4 и 1 встречаются у отдельных объектов;
# они интерпретируются как полосы, поскольку веер даёт вырождения и перекрытия.
PRIM_LIST = 3
PRIM_STRIPS = (1, 4)


def corner_order(prim: Primitive) -> np.ndarray:
    """Indices into the primitive's corners that form a plain triangle list."""
    n = len(prim.vertex_indices)
    kind = prim.flags & 0xFF
    if kind not in PRIM_STRIPS:
        return np.arange(n - n % 3)
    vi = prim.vertex_indices
    out = []
    for i in range(n - 2):
        tri = (i, i + 1, i + 2) if i % 2 == 0 else (i + 1, i, i + 2)
        if len({int(vi[k]) for k in tri}) == 3:  # Пропускаем вырожденные треугольники между полосами.
            out.extend(tri)
    return np.array(out, dtype=int)


def _floats(part, width):
    return np.frombuffer(part.data, "<f4").reshape(-1, width)


def article_transform(art: Article, group: int):
    """4x4 row-vector transform from a "tr" part (translation in the last row)."""
    tr = art.find("tr", group)
    if not tr:
        tr = art.find("tr")
        if len(tr) != 1:  # Матриц несколько, но подходящей для этой группы нет.
            return None
    return np.frombuffer(tr[0].data[:64], "<f4").reshape(4, 4)


def article_mesh(art: Article, lod=1, damage=0):
    """Mesh of one article at one LOD as flat triangle arrays.

    Returns None when the article has no geometry at that LOD, otherwise a
    dict with float32 arrays positions (N,3), normals (N,3), uvs (N,2),
    uint8 colors (N,4) (white when the article has no "df" stream) and a
    list of (material, first_vertex, vertex_count) draw ranges. Vertices are
    de-indexed because positions and uvs use separate index streams.
    """
    prims = [parse_primitive(p) for p in art.find("pr") if (p.index >> 12) == lod]
    if not prims:
        return None
    pos, nrm, tex, col, draws = [], [], [], [], []
    for prim in prims:
        voff, _vlen, group = prim.streams[STREAM_VERTEX]
        vt = art.find("vt", (damage << 4) | group) or art.find("vt", group)
        nm = art.find("nm", (damage << 4) | group) or art.find("nm", group)
        uv = art.find("uv", group)
        v = _floats(vt[0], 4)[:, :3]
        n = _floats(nm[0], 4)[:, :3] if nm else np.zeros_like(v)
        t = _floats(uv[0], 2) if uv else np.zeros((1, 2), np.float32)
        vi = prim.vertex_indices.astype(int) + voff // 16
        if STREAM_UV in prim.streams and uv:
            ui = prim.uv_indices.astype(int) + prim.streams[STREAM_UV][0] // 8
        else:
            ui = np.zeros_like(vi)
        c = np.full((len(vi), 4), 255, np.uint8)
        if STREAM_COLOR in prim.streams:
            coff, _clen, cgroup = prim.streams[STREAM_COLOR]
            df = art.find("df", cgroup)
            if df:
                allc = np.frombuffer(df[0].data, np.uint8).reshape(-1, 4)
                c = allc[coff // 4:coff // 4 + len(vi)]
        order = corner_order(prim)
        vi, ui, c = vi[order], ui[order], c[order]
        m = article_transform(art, group)
        pv, pn = v[vi], n[vi]
        if m is not None:
            pv = pv @ m[:3, :3] + m[3, :3]
            pn = pn @ m[:3, :3]
        draws.append((prim.material, sum(len(x) for x in pos), len(vi)))
        pos.append(pv)
        nrm.append(pn)
        tex.append(t[ui])
        col.append(c)
    return {
        "positions": np.concatenate(pos).astype(np.float32),
        "normals": np.concatenate(nrm).astype(np.float32),
        "uvs": np.concatenate(tex).astype(np.float32),
        "colors": np.concatenate(col),
        "draws": draws,
    }
