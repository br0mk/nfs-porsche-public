"""EA SHPI ("FSH") texture archive reader.

Layout: "SHPI", u32 file size, u32 entry count, 4-byte directory id, then
<count> x (4-byte name, u32 offset). Every entry is a chain of 16-byte-header
blocks: u8 code, u24 offset to next block (0 = last), then for image blocks
u16 width, u16 height, 4 x u16 centre/position fields.
"""
import struct
from dataclasses import dataclass, field

import numpy as np

# Код → число байтов на пиксель; только блоки изображений.
IMAGE_CODES = {
    0x7B: 1,   # 8-битные индексы палитры.
    0x78: 2,   # RGB565
    0x7E: 2,   # ARGB1555
    0x6D: 2,   # ARGB4444
    0x7F: 3,   # RGB888; в файле порядок BGR.
    0x7D: 4,   # ARGB8888; в файле порядок BGRA.
    0x60: 0,   # DXT1
    0x61: 0,   # DXT3
}
PALETTE_CODES = {0x22, 0x24, 0x29, 0x2A, 0x2D}


@dataclass
class Block:
    code: int
    data: bytes          # Данные после 16-байтового заголовка.
    header: bytes


@dataclass
class Entry:
    name: str
    code: int
    width: int
    height: int
    center: tuple
    position: tuple
    pixels: bytes
    attachments: list = field(default_factory=list)

    def palette(self):
        for b in self.attachments:
            if b.code in PALETTE_CODES:
                return b
        return None


def _decode_palette(block: Block) -> np.ndarray:
    count = struct.unpack_from("<H", block.header, 4)[0]
    raw = block.data
    if block.code == 0x24:  # RGB888
        a = np.frombuffer(raw[:count * 3], np.uint8).reshape(-1, 3)
        rgba = np.concatenate([a[:, ::-1], np.full((len(a), 1), 255, np.uint8)], 1)
    elif block.code == 0x29:  # RGB565
        rgba = _expand16(np.frombuffer(raw[:count * 2], "<u2"), 0x78)
    elif block.code in (0x2A, 0x22):  # ARGB8888 (BGRA)
        a = np.frombuffer(raw[:count * 4], np.uint8).reshape(-1, 4)
        rgba = a[:, [2, 1, 0, 3]].copy()
    elif block.code == 0x2D:  # ARGB1555
        rgba = _expand16(np.frombuffer(raw[:count * 2], "<u2"), 0x7E)
    else:
        raise ValueError(f"palette code {block.code:#x}")
    return rgba


def _expand16(v: np.ndarray, code: int) -> np.ndarray:
    v = v.astype(np.uint32)
    if code == 0x78:
        r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
        return np.stack([r * 255 // 31, g * 255 // 63, b * 255 // 31,
                         np.full_like(v, 255)], -1).astype(np.uint8)
    if code == 0x7E:
        a, r, g, b = (v >> 15) & 1, (v >> 10) & 31, (v >> 5) & 31, v & 31
        return np.stack([r * 255 // 31, g * 255 // 31, b * 255 // 31,
                         a * 255], -1).astype(np.uint8)
    if code == 0x6D:
        a, r, g, b = (v >> 12) & 15, (v >> 8) & 15, (v >> 4) & 15, v & 15
        return np.stack([r * 17, g * 17, b * 17, a * 17], -1).astype(np.uint8)
    raise ValueError(code)


def _dxt_color(c0, c1, dxt1):
    def rgb(c):
        return np.array([((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63,
                         (c & 31) * 255 // 31, 255], np.int32)
    p0, p1 = rgb(c0), rgb(c1)
    if c0 > c1 or not dxt1:
        return [p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3]
    return [p0, p1, (p0 + p1) // 2, np.array([0, 0, 0, 0])]


def _decode_dxt(data, w, h, code):
    out = np.zeros((h, w, 4), np.uint8)
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    stride = 8 if code == 0x60 else 16
    p = 0
    for by in range(bh):
        for bx in range(bw):
            blk = data[p:p + stride]
            p += stride
            alpha = None
            if code == 0x61:
                a = int.from_bytes(blk[:8], "little")
                alpha = [((a >> (4 * i)) & 15) * 17 for i in range(16)]
                blk = blk[8:]
            c0, c1, bits = struct.unpack("<HHI", blk)
            cols = _dxt_color(c0, c1, code == 0x60)
            for i in range(16):
                y, x = by * 4 + i // 4, bx * 4 + i % 4
                if y < h and x < w:
                    px = cols[(bits >> (2 * i)) & 3].copy()
                    if alpha is not None:
                        px[3] = alpha[i]
                    out[y, x] = px
    return out


def entry_rgba(e: Entry) -> np.ndarray:
    """Return an (h, w, 4) uint8 RGBA array for an image entry."""
    w, h = e.width, e.height
    if e.code == 0x7B:
        pal_block = e.palette()
        if pal_block is None:
            raise ValueError(f"{e.name}: indexed image without palette")
        pal = _decode_palette(pal_block)
        idx = np.frombuffer(e.pixels[:w * h], np.uint8).reshape(h, w)
        pal = np.concatenate([pal, np.zeros((256 - len(pal), 4), np.uint8)]) if len(pal) < 256 else pal
        return pal[idx]
    if e.code in (0x78, 0x7E, 0x6D):
        v = np.frombuffer(e.pixels[:w * h * 2], "<u2").reshape(h, w)
        return _expand16(v, e.code)
    if e.code == 0x7F:
        a = np.frombuffer(e.pixels[:w * h * 3], np.uint8).reshape(h, w, 3)
        return np.concatenate([a[..., ::-1], np.full((h, w, 1), 255, np.uint8)], -1)
    if e.code == 0x7D:
        a = np.frombuffer(e.pixels[:w * h * 4], np.uint8).reshape(h, w, 4)
        return a[..., [2, 1, 0, 3]].copy()
    if e.code in (0x60, 0x61):
        return _decode_dxt(e.pixels, w, h, e.code)
    raise ValueError(f"{e.name}: unsupported image code {e.code:#x}")


def _pixel_bytes(code, w, h):
    bpp = IMAGE_CODES[code]
    if code == 0x60:
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8
    if code == 0x61:
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
    return w * h * bpp


@dataclass
class Archive:
    dir_id: str
    entries: list

    def by_name(self, name):
        for e in self.entries:
            if e.name == name:
                return e
        raise KeyError(name)


def parse(data: bytes) -> Archive:
    magic, size, count, dir_id = struct.unpack_from("<4sII4s", data, 0)
    if magic != b"SHPI":
        raise ValueError("not an SHPI archive")
    dirents = [struct.unpack_from("<4sI", data, 16 + 8 * i) for i in range(count)]
    ends = sorted({off for _, off in dirents} | {len(data)})
    entries = []
    for name, off in dirents:
        limit = next(x for x in ends if x > off)
        blocks = []
        p = off
        while True:
            hdr = data[p:p + 16]
            code = hdr[0]
            nxt = int.from_bytes(hdr[1:4], "little")
            end = p + nxt if nxt else limit
            blocks.append(Block(code, data[p + 16:end], hdr))
            if not nxt:
                break
            p += nxt
        img = blocks[0]
        w, h, cx, cy, px, py = struct.unpack_from("<6H", img.header, 4)
        code, pixels = img.code, img.data
        if code & 0x80:  # Старший бит означает, что пиксели сжаты RefPack.
            from . import refpack
            code &= 0x7F
            pixels = refpack.decompress(pixels)
        if code not in IMAGE_CODES:
            raise ValueError(f"{name!r}: first block code {img.code:#x} is not an image")
        n = _pixel_bytes(code, w, h)
        if len(pixels) < n:
            raise ValueError(f"{name!r}: {len(pixels)} pixel bytes, need {n}")
        entries.append(Entry(name.decode("latin-1"), code, w, h, (cx, cy),
                             (px, py), pixels[:n], blocks[1:]))
    return Archive(dir_id.decode("latin-1"), entries)


def load(path) -> Archive:
    from . import refpack
    return parse(refpack.load(path))
