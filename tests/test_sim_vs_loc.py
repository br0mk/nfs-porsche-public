"""Cross-check decoded .sim fields against the game's own spec cards (.loc).

Run: PYTHONPATH=src python3 -m pytest tests  (needs the extracted disc under
work/selected-disc-joliet; tests are skipped when it is absent).
"""
import glob
import re
from pathlib import Path

import pytest

from nfs5 import loc, sim

DISC = Path(__file__).resolve().parents[1] / "work" / "selected-disc-joliet"
pytestmark = pytest.mark.skipif(not DISC.is_dir(), reason="game data not extracted")


SYNONYMS = {"speedster": "speed", "hardtop": "hard", "roadster": "road",
            "cabriolet": "cabrio", "turbo": "t", "convertible": "conv"}


def _tokens(title):
    t = title.lower().replace("(", " ").replace(")", " ").replace("-", " ")
    t = re.sub(r"(\d\.\d)l\b", r"\1", t)          # 1.6L -> 1.6
    t = re.sub(r"(\d\.\d)s(\d*)\b", r"\1 s \2", t)   # 1.6S90 -> 1.6 s 90
    t = re.sub(r"\bs(\d+)\b", r"s \1", t)                # S90 -> s 90
    t = re.sub(r"\b(356|550|911|944|914/4|914)([a-z]+)\b", r"\1 \2", t)  # 356A, 911S
    t = re.sub(r"(\d{4})(\d{3})", r"\1 \2", t)          # 1951356 -> 1951 356
    t = re.sub(r"(cabrio|coupe)(\d)", r"\1 \2", t)
    toks = {SYNONYMS.get(w, w) for w in t.split() if w}
    toks.discard("911")
    toks.discard("d")
    return {w.replace("914/4", "914") for w in toks}


def _match(sim_title, card_title):
    a, b = _tokens(sim_title), _tokens(card_title)
    year = lambda ts: {w for w in ts if re.fullmatch(r"(19|20)\d\d", w)}
    if not year(a) or year(a) != year(b):
        return 0.0
    return len(a & b) / len(a | b)


def _num(text):
    m = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(m.group()) if m else None


def pairs():
    sims = list(map(sim.load, glob.glob(str(DISC / "GameData/Simulation/CarData/*.sim"))))
    out = []
    for path in sorted(glob.glob(str(DISC / "FEData/Locale/*.loc"))):
        card = loc.car_card(path)
        title = card.get("title") or ""
        if not title or "gear_1" not in card:
            continue
        scored = sorted(((_match(s["title"], title), i) for i, s in enumerate(sims)), reverse=True)
        (score, best), runner_up = scored[0], scored[1][0]
        # Принимаем только достаточно точные и однозначные соответствия.
        if score >= 0.85 and runner_up < score:
            out.append((card, sims[best]))
    return out


# (Поле карточки, поле SIM, допуск). Карточки содержат справочные характеристики,
# а SIM-файлы настроены для игры, поэтому отдельные значения могут отличаться
# (например, коробка 996 Turbo и задняя передача 944); проверяем общее согласие.
CHECKS = [
    ("gear_1", "gear_1", 0.02), ("gear_2", "gear_2", 0.02), ("gear_3", "gear_3", 0.02),
    ("gear_4", "gear_4", 0.02), ("gear_reverse", "gear_reverse", 0.02),
    ("final_drive", "final_drive", 0.02), ("redline", "redline_rpm", 1),
    ("wheelbase", "wheelbase_mm", 1), ("top_speed", "top_speed_mph", 1.5),
]
MIN_AGREEMENT = 0.85


def test_enough_matches():
    assert len(pairs()) >= 45


@pytest.mark.parametrize("card_field,sim_field,tol", CHECKS)
def test_field_agrees_with_spec_cards(card_field, sim_field, tol):
    rows = [(c["title"], _num(c[card_field]), s[sim_field]) for c, s in pairs()
            if _num(c.get(card_field, "")) is not None]
    agree = [r for r in rows if abs(r[1] - r[2]) <= tol]
    assert len(rows) >= 40
    assert len(agree) / len(rows) >= MIN_AGREEMENT, [r for r in rows if r not in agree]


def test_peak_torque_matches_curve():
    rows = [(c["title"], _num(c["torque"]), max(s["torque_curve_lbft"])) for c, s in pairs()
            if _num(c["torque"])]
    agree = [r for r in rows if abs(r[1] - r[2]) <= 3]
    assert len(agree) / len(rows) >= MIN_AGREEMENT


def test_gear_count_and_layout():
    rows = pairs()
    bad = []
    for c, s in rows:
        n = _num(c["gearbox"])
        if n and n != s["gear_count"]:
            bad.append((c["title"], c["gearbox"], s["gear_count"]))
        layout = c["layout"].lower()
        want = 2 if layout.startswith("front") else 1 if layout.startswith("mid") else 0
        if s["engine_layout"] != want:
            bad.append((c["title"], c["layout"], s["engine_layout"]))
    assert len(bad) <= len(rows) * (1 - MIN_AGREEMENT), bad
