"""Tolerant reader for the game's INI-like text files (.tpg, .clr, .ini)."""


def parse(text: str) -> dict:
    out, sect = {}, None
    for line in text.replace("\r", "").split("\n"):
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            sect = out.setdefault(line[1:-1], {})
        elif "=" in line and sect is not None:
            k, v = line.split("=", 1)
            sect[k.strip()] = v.strip()
    return out


def load(path) -> dict:
    with open(path, "rb") as f:
        return parse(f.read().decode("latin-1"))
