"""Dump every image of an FSH archive (or a CRP-embedded one) to PNG files."""
import sys
from pathlib import Path

from PIL import Image

from . import fsh


def dump(archive, out_dir: Path, prefix=""):
    out_dir.mkdir(parents=True, exist_ok=True)
    seen = {}
    paths = []
    for i, e in enumerate(archive.entries):
        name = e.name.strip().replace("/", "_") or f"{i:03d}"
        k = seen.get(name, 0)
        seen[name] = k + 1
        if k:
            name = f"{name}_{k}"
        path = out_dir / f"{prefix}{name}.png"
        Image.fromarray(fsh.entry_rgba(e), "RGBA").save(path)
        paths.append(path)
    return paths


def main(argv):
    src, out = Path(argv[1]), Path(argv[2])
    for p in dump(fsh.load(src), out):
        print(p)


if __name__ == "__main__":
    main(sys.argv)
