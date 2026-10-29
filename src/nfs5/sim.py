"""Car simulation parameter files (GameData/Simulation/CarData/*.sim).

Every file is 328 bytes: a 64-byte NUL-terminated title, then 66 little-endian
32-bit fields. Field meanings below were inferred by comparing all 86 files
with each other and with the spec cards in FEData/Locale/*.loc. "confirmed"
means the value matches the spec card (or real-world data) across the cars
checked by tests/test_sim_vs_loc.py; "inferred" means a consistent pattern
without an independent reference; unnamed fields stay as raw values.
"""
import struct

SIZE = 328
TORQUE_POINTS = 21     # 21 число float начиная со смещения 156; уточнено по анализу игры.
TORQUE_RPM_STEP = 500  # Шаг 500 об/мин соответствует интерполяции по rpm × 0,002.

# Смещение: (имя, тип, степень уверенности).
FIELDS = {
    64: ("mass_kg", "f", "inferred: spec card weight + ~40 kg"),
    68: ("wheelbase_mm", "f", "confirmed; code: * 0.001"),
    72: ("engine_layout", "i", "confirmed: 0 rear, 1 mid, 2 front"),
    76: ("turbo", "i", "confirmed"),
    80: ("gear_count", "i", "confirmed; code: +2 for reverse and neutral"),
    84: ("unknown_84", "i", ""),
    88: ("drive_percent_88", "f", "code: * 0.01, multiplies per-gear force factors"),
    92: ("front_drive_percent", "f", "inferred: non-zero only on 4WD models; code: * 0.01"),
    96: ("gear_reverse", "f", "confirmed"),
    100: ("gear_neutral", "f", "inferred"),
    104: ("gear_1", "f", "confirmed"),
    108: ("gear_2", "f", "confirmed"),
    112: ("gear_3", "f", "confirmed"),
    116: ("gear_4", "f", "confirmed"),
    120: ("gear_5", "f", "confirmed"),
    124: ("gear_6", "f", "confirmed"),
    128: ("final_drive", "f", "confirmed"),
    132: ("tyre_width_mm", "f", "code: circumference = pi*(rim*25.4 + 2*width*aspect/100) mm"),
    136: ("tyre_aspect", "f", "code"),
    140: ("rim_inches", "f", "code"),
    144: ("top_speed_mph", "f", "confirmed; code: * 0.44642857 (mph -> m/s)"),
    148: ("redline_rpm", "f", "confirmed; code: 1/redline cached"),
    152: ("unknown_152", "f", ""),
    # 156–236: кривая момента из 21 точки; см. TORQUE_POINTS.
    240: ("unknown_240", "f", ""),
    244: ("unknown_244_grip", "f", "inferred: highest on race cars"),
    248: ("unknown_248", "f", ""),
    252: ("unknown_252", "f", ""),
    260: ("unknown_260", "f", ""),
    264: ("unknown_264", "f", ""),
    268: ("unknown_268_front_aero", "f", "inferred: >1 on race cars"),
    272: ("unknown_272_rear_aero", "f", "inferred: >1 on race cars"),
    276: ("unknown_276_front", "f", ""),
    280: ("unknown_280_rear", "f", ""),
    284: ("unknown_284", "f", ""),
    292: ("unknown_292", "f", ""),
    296: ("unknown_296", "f", ""),
    300: ("unknown_300", "f", ""),
    304: ("scale_304", "f", "always 1.0"),
    308: ("scale_308", "f", "always 1.0"),
    312: ("scale_312", "f", "always 1.0"),
    316: ("scale_316", "f", "always 1.0"),
    320: ("scale_320", "f", ""),
    324: ("scale_324", "f", ""),
}


def parse(data: bytes) -> dict:
    if len(data) != SIZE:
        raise ValueError(f"expected {SIZE} bytes, got {len(data)}")
    out = {"title": data[:64].split(b"\0", 1)[0].decode("latin-1").strip()}
    for off, (name, typ, _status) in FIELDS.items():
        out[name] = struct.unpack_from("<" + typ, data, off)[0]
    out["torque_curve_lbft"] = list(struct.unpack_from(f"<{TORQUE_POINTS}f", data, 156))
    known = set(FIELDS) | set(range(156, 156 + 4 * TORQUE_POINTS, 4))
    out["unnamed"] = {off: struct.unpack_from("<I", data, off)[0]
                      for off in range(64, SIZE, 4) if off not in known}
    return out


def load(path) -> dict:
    with open(path, "rb") as f:
        return parse(f.read())
