"""Export every car in GameData/CarModel and report failures."""
import json
import sys
import time
from pathlib import Path

from . import export
from .car import CarModel


def main(argv):
    car_dir, out = Path(argv[1]), Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    names = sorted(p.stem for p in car_dir.glob("*.crp"))
    ok, report = [], {}
    for name in names:
        t = time.time()
        try:
            model = CarModel(car_dir, name)
            tris = export.write_glb(model, out / f"{name}.glb")
            report[name] = {"triangles": tris, "articles": len(model.crp.articles),
                            "pages": len(model.pages), "seconds": round(time.time() - t, 2)}
            ok.append(name)
        except Exception as ex:  # Сообщаем об ошибке и продолжаем обзор остальных файлов.
            report[name] = {"error": f"{type(ex).__name__}: {ex}"}
        print(name, report[name], flush=True)
    (out / "index.json").write_text(json.dumps(ok))
    (out / "report.json").write_text(json.dumps(report, indent=1))
    print(f"{len(ok)}/{len(names)} exported")


if __name__ == "__main__":
    main(sys.argv)
