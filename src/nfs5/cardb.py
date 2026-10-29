"""FEData/Data/nfs5.car: the front-end car table.

109 fixed records of 1648 bytes (109 * 1648 = file size). Observed C-string
fields: display name at 2, spec card (.loc) at 77, model (CarModel/<x>.crp)
at 127, simulation file (Simulation/CarData/<x>.sim) at 177. The rest
(front-end graph data, colours) is not decoded.
"""
from dataclasses import dataclass

RECORD = 1648


@dataclass
class CarEntry:
    name: str
    card: str
    model: str
    sim: str


def _cstr(b, off, n=50):
    return b[off:off + n].split(b"\0", 1)[0].decode("latin-1").strip()


def parse(data: bytes):
    if len(data) % RECORD:
        raise ValueError("unexpected nfs5.car size")
    out = []
    for i in range(0, len(data), RECORD):
        r = data[i:i + RECORD]
        out.append(CarEntry(_cstr(r, 2, 50), _cstr(r, 77), _cstr(r, 127), _cstr(r, 177)))
    return out


def load(path):
    with open(path, "rb") as f:
        return parse(f.read())
