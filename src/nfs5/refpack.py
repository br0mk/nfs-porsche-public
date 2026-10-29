"""RefPack (EA "QFS") LZ77 decompressor.

Header: 2-byte big-endian flags/magic (low byte 0xFB), optional 3/4-byte
compressed size when flag 0x01 is set, then a 3-byte (or 4-byte when flag
0x80 is set) big-endian uncompressed size.
"""


def is_refpack(data: bytes) -> bool:
    return len(data) >= 5 and data[1] == 0xFB and (data[0] & 0x3E) == 0x10


def decompress(data: bytes) -> bytes:
    if not is_refpack(data):
        raise ValueError("not a RefPack stream")
    flags = data[0]
    size_len = 4 if flags & 0x80 else 3
    pos = 2
    if flags & 0x01:
        pos += size_len
    out_len = int.from_bytes(data[pos:pos + size_len], "big")
    pos += size_len

    out = bytearray(out_len)
    o = 0
    n = len(data)
    while pos < n:
        b0 = data[pos]
        if b0 < 0x80:  # Команда длиной 2 байта.
            b1 = data[pos + 1]
            pos += 2
            lit = b0 & 0x03
            length = ((b0 & 0x1C) >> 2) + 3
            dist = ((b0 & 0x60) << 3) + b1 + 1
        elif b0 < 0xC0:  # Команда длиной 3 байта.
            b1, b2 = data[pos + 1], data[pos + 2]
            pos += 3
            lit = b1 >> 6
            length = (b0 & 0x3F) + 4
            dist = ((b1 & 0x3F) << 8) + b2 + 1
        elif b0 < 0xE0:  # Команда длиной 4 байта.
            b1, b2, b3 = data[pos + 1], data[pos + 2], data[pos + 3]
            pos += 4
            lit = b0 & 0x03
            length = ((b0 & 0x0C) << 6) + b3 + 5
            dist = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
        elif b0 < 0xFC:  # Серия литералов.
            pos += 1
            lit = ((b0 & 0x1F) + 1) * 4
            out[o:o + lit] = data[pos:pos + lit]
            o += lit
            pos += lit
            continue
        else:  # Конец потока с 0–3 завершающими литералами.
            pos += 1
            lit = b0 & 0x03
            out[o:o + lit] = data[pos:pos + lit]
            o += lit
            break

        out[o:o + lit] = data[pos:pos + lit]
        o += lit
        pos += lit
        src = o - dist
        if src < 0:
            raise ValueError(f"back-reference before start at out={o}")
        for i in range(length):  # Копируем последовательно: перекрытие допустимо.
            out[o + i] = out[src + i]
        o += length

    if o != out_len:
        raise ValueError(f"size mismatch: header {out_len}, produced {o}")
    return bytes(out)


def load(path) -> bytes:
    with open(path, "rb") as f:
        data = f.read()
    return decompress(data) if is_refpack(data) else data
