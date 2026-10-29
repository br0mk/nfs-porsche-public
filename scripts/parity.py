"""Compare the Swift port (native/ nfs5car) with the Python reference.

Usage: PYTHONPATH=src python3 scripts/parity.py <CarModel dir> <nfs5car binary> [<Track dir>]
Both sides print triangle count, page count, a positional checksum and a
texture-page pixel checksum per car.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

from nfs5 import export
from nfs5.car import CarModel


def python_side(car_dir):
    out = {}
    for crp in sorted(Path(car_dir).glob("*.crp")):
        m = CarModel(car_dir, crp.stem)
        groups = export._groups(m, 1)
        tris = sum(len(g["p"]) // 3 for g in groups.values())
        p = np.concatenate([g["p"] for g in groups.values()]).astype(np.float64)
        checksum = float((p[:, 0] + 2 * p[:, 1] + 3 * p[:, 2]).sum())
        texsum = 0
        for i, page in m.pages.items():
            flat = page.rgba.reshape(-1).astype(np.int64)
            texsum += int((flat * ((np.arange(flat.size) % 7) + i + 1)).sum())
        out[crp.stem] = (tris, len(m.pages), checksum, texsum)
    return out


def swift_side(car_dir, binary):
    res = subprocess.run([binary, str(car_dir)], capture_output=True, text=True)
    out = {}
    for line in res.stdout.splitlines():
        name, *kv = line.split()
        d = dict(x.split("=") for x in kv if "=" in x)
        out[name] = (int(d["triangles"]), int(d["pages"]), float(d["checksum"]), int(d["texsum"]))
    return out


def track_python_side(track_dir):
    from nfs5.track import Track
    out = {}
    for crp in sorted(Path(track_dir).glob("*.crp")):
        t = Track(track_dir, crp.stem)
        b = t.batches()
        p = np.concatenate([x["p"] for x in b]).astype(np.float64)
        c = np.concatenate([x["c"] for x in b]).astype(np.float64)
        out[crp.stem] = (sum(len(x["p"]) // 3 for x in b), len(b),
                         float((p[:, 0] + 2 * p[:, 1] + 3 * p[:, 2]).sum()),
                         float((c[:, 0] + 2 * c[:, 1] + 3 * c[:, 2]).sum()),
                         max(len(ch) for ch in t.road()))
    return out


def track_swift_side(track_dir, binary):
    res = subprocess.run([binary, "--tracks", str(track_dir)], capture_output=True, text=True)
    out = {}
    for line in res.stdout.splitlines():
        name, *kv = line.split()
        d = dict(x.split("=") for x in kv if "=" in x)
        out[name] = (int(d["triangles"]), int(d["batches"]), float(d["checksum"]),
                     float(d["colorsum"]), int(d["road"]))
    return out


def _close(a, b, rel=1e-6):
    return abs(a - b) <= rel * max(1.0, abs(a), abs(b))


def main(argv):
    py, sw = python_side(argv[1]), swift_side(argv[1], argv[2])
    bad = [(k, py[k], sw.get(k)) for k in py
           if k not in sw or py[k][:2] != sw[k][:2] or abs(py[k][2] - sw[k][2]) > 0.05
           or py[k][3] != sw[k][3]]
    print(f"{len(py) - len(bad)}/{len(py)} cars identical")
    if len(argv) > 3:
        tp, ts = track_python_side(argv[3]), track_swift_side(argv[3], argv[2])
        tbad = [(k, tp[k], ts.get(k)) for k in tp
                if k not in ts or tp[k][:2] != ts[k][:2] or tp[k][4] != ts[k][4]
                or not _close(tp[k][2], ts[k][2]) or not _close(tp[k][3], ts[k][3])]
        print(f"{len(tp) - len(tbad)}/{len(tp)} tracks identical")
        bad += tbad
    for b in bad:
        print("MISMATCH", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
