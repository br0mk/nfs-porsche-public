"""LOC string tables (FEData/Locale): "LOCH" header, "LOCI" index, one "LOCL"
block per language.

LOCH: u32 header size, u32 ?, u32 language count, then one u32 file offset
per block (LOCI first, then each LOCL). LOCL: u32 size, u32 0, u32 string
count, then u32 string offsets relative to the LOCL tag; strings are
NUL-terminated Latin-1.
"""
import struct


def parse(data: bytes):
    tag, _hsize, _one, nlang = struct.unpack_from("<4sIII", data, 0)
    if tag != b"LOCH":
        raise ValueError("not a LOC file")
    offsets = struct.unpack_from(f"<{nlang}I", data, 16)
    langs = []
    for off in offsets:
        if data[off:off + 4] != b"LOCL":
            continue
        _size, _zero, count = struct.unpack_from("<III", data, off + 4)
        sofs = struct.unpack_from(f"<{count}I", data, off + 16)
        langs.append([data[off + s:data.index(b"\0", off + s)].decode("latin-1") for s in sofs])
    return langs


def load(path):
    with open(path, "rb") as f:
        return parse(f.read())


# Назначение строк карточки автомобиля в английском языковом блоке, по индексу.
CAR_CARD = {0: "title", 3: "engine", 4: "displacement", 5: "power", 6: "torque",
            7: "zero_to_sixty_s", 8: "top_speed", 11: "weight", 12: "length",
            13: "width", 14: "height", 15: "wheelbase", 24: "redline",
            25: "compression", 28: "layout", 29: "brakes_front", 30: "brakes_rear",
            31: "wheels_front", 32: "wheels_rear", 33: "tyres_front", 34: "tyres_rear",
            35: "gear_1", 36: "gear_2", 37: "gear_3", 38: "gear_4", 39: "gear_5",
            40: "gear_6", 41: "final_drive", 42: "gear_reverse", 43: "gearbox",
            44: "transmission"}


def car_card(path):
    eng = load(path)[0]
    return {k: eng[i] for i, k in CAR_CARD.items() if i < len(eng)}
