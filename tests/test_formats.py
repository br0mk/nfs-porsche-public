"""Whole-disc smoke tests for the reconstructed format readers."""
import glob
from pathlib import Path

import numpy as np
import pytest

from nfs5 import crp, fsh, refpack
from nfs5.car import CarModel

DISC = Path(__file__).resolve().parents[1] / "work" / "selected-disc-joliet"
CARS = DISC / "GameData" / "CarModel"
pytestmark = pytest.mark.skipif(not DISC.is_dir(), reason="game data not extracted")


def test_refpack_sizes_match_headers():
    files = sorted(CARS.glob("*.crp"))
    assert len(files) == 40
    for f in files:
        raw = f.read_bytes()
        assert refpack.is_refpack(raw)
        out = refpack.decompress(raw)  # При любом несоответствии размера возникает исключение.
        assert out[:4] == b" raC"


def test_every_fsh_image_decodes():
    files = sorted(set(glob.glob(str(DISC / "**/*.[fF][sS][hH]"), recursive=True)))
    assert len(files) >= 500
    images = 0
    for f in files:
        for e in fsh.load(f).entries:
            rgba = fsh.entry_rgba(e)
            assert rgba.shape == (e.height, e.width, 4)
            images += 1
    assert images >= 10000


def test_356_structure():
    car = crp.load(CARS / "356_1.crp")
    assert len(car.articles) == 115
    names = [a.name.strip() for a in car.articles]
    assert {"Body", "WheelFront", "WheelRear", "Interior", "Steer"} <= set(names)
    body = crp.article_mesh(car.articles[names.index("Body")], lod=1)
    size = body["positions"].max(0) - body["positions"].min(0)
    # Ширина настоящей 356 — 1,66 м; длина модели кузова без бамперов — около 3,6 м.
    assert 1.6 < size[0] < 1.75 and 3.4 < size[2] < 3.9


def test_primitive_indices_in_range_for_all_cars():
    for f in sorted(CARS.glob("*.crp")):
        car = crp.load(f)
        for art in car.articles:
            for lod in range(1, 8):
                m = crp.article_mesh(art, lod)
                if m is None:
                    continue
                assert np.isfinite(m["positions"]).all(), (f.name, art.name)
                assert len(m["positions"]) % 3 == 0


def test_car_pages_built():
    model = CarModel(CARS, "356_1")
    assert len(model.pages) == 11
    a, b = model.pages[0].rgba, model.pages[1].rgba
    assert a.shape == b.shape
    # Зеркальная страница: картинка фары 48×48 в позиции (0,0) отражается на своём месте.
    assert (b[:48, :48] == a[:48, :48][:, ::-1]).all()
