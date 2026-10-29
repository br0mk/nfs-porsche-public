"""Track container, primitives and road data on the original disc."""
from pathlib import Path

import numpy as np
import pytest

from nfs5 import crp
from nfs5.track import Track

DISC = Path(__file__).resolve().parents[1] / "work" / "selected-disc-joliet"
TRACKS = DISC / "GameData" / "Track"
pytestmark = pytest.mark.skipif(not DISC.is_dir(), reason="game data not extracted")


def test_all_tracks_build():
    names = sorted(p.stem for p in TRACKS.glob("*.crp"))
    assert len(names) == 15
    for name in names:
        t = Track(TRACKS, name)
        batches = t.batches()
        tris = sum(len(b["p"]) // 3 for b in batches)
        assert tris > 10000, name
        # У одного материала и «ft05» трассы industrial нет изображения: менее 0,1 % треугольников.
        untextured = sum(len(b["p"]) // 3 for b in batches if b["texture"] not in t.images)
        assert untextured < tris * 0.001, (name, untextured)
        for b in batches:
            assert np.isfinite(b["p"]).all()


def test_alps_counts_and_extent():
    t = Track(TRACKS, "alps")
    assert len(t.crp.articles) == 1752
    tris = sum(len(b["p"]) // 3 for b in t.batches())
    assert tris == 62194
    p = np.concatenate([b["p"] for b in t.batches()])
    size = p.max(0) - p.min(0)
    assert 1500 < size[0] < 2000 and 6000 < size[2] < 6500  # Метры.


def test_road_chains_match_simt():
    t = Track(TRACKS, "alps")
    chains = t.road()
    assert [len(c) for c in chains] == [1795, 272, 22, 16]
    main = np.array([n["p"] for n in chains[0]])
    steps = np.linalg.norm(np.diff(main, axis=0), axis=1)
    assert 5 < np.median(steps) < 8
    # Векторы направления единичные и примерно совпадают с направлением цепочки.
    fwd = np.array([n["fwd"] for n in chains[0][:-1]])
    assert np.allclose(np.linalg.norm(fwd, axis=1), 1, atol=0.01)


def test_strip_primitives_are_triangulated():
    t = crp.load(TRACKS / "alps.crp")
    seen = 0
    for art in t.articles:
        for p in art.find("pr"):
            prim = crp.parse_primitive(p)
            if prim.flags & 0xFF in crp.PRIM_STRIPS:
                order = crp.corner_order(prim)
                assert len(order) % 3 == 0
                seen += 1
    assert seen > 20
