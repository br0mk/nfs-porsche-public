# NFS5 Format Tools

Unofficial Python and Swift tools for inspecting data formats used by the PC
edition of *Need for Speed: Porsche Unleashed* (2000). Includes readers, model
exporters, and a command-line tool for comparing the Swift and Python output.

This repository contains no game executable, reconstructed game functions, game
assets, screenshots, or extracted game files. It is not a playable port.

## License and scope

The project source and documentation in this repository are offered under the
[MIT License](LICENSE). That license does not cover the original game, user-supplied
files, exported assets, third-party dependencies, or trademarks. No affiliation
with or endorsement by Electronic Arts or Porsche is implied.

See [publication scope](docs/PUBLICATION.md), [dependency notices](THIRD_PARTY_NOTICES.md),
and [format notes](docs/FORMATS.md). No formal clean-room process is claimed.

## Contents

- `src/nfs5/`: RefPack, FSH, CRP, INI, SIM, LOC, car and track readers; glTF/OBJ export.
- `native/`: Swift format readers and the `nfs5car` command-line comparison tool.
- `tests/`: synthetic tests and optional local-data integration tests.
- `scripts/`: cross-language comparison and publication checks.

## Python setup and tests

Python 3.10 or newer is required.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
```

Synthetic tests run without the game. Integration tests skip when local data is
absent; a skipped test is not evidence of game compatibility. The readers are
research tools and are not hardened parsers for hostile input.

## Local data

Supply data only when your copy, license, and applicable law permit the intended
use. Place an existing extracted data tree at `work/selected-disc-joliet/`, retaining
its long filenames and `GameData/` and `FEData/` directories. This project does not
provide downloads, DRM-removal tools, or instructions for bypassing copy protection.

Data, exports, and build output are ignored by Git. An MIT license for the tools does
not grant rights to their inputs or to material reproduced in their output.

## Export models and tracks

```sh
python -m nfs5.batch work/selected-disc-joliet/GameData/CarModel out/models
python -m nfs5.track work/selected-disc-joliet/GameData/Track out/tracks
```

The exported files may contain game-derived material. Keep them local unless you
have a separate basis for distributing them.

## Swift readers

Requires macOS 13 or newer and a Swift toolchain supporting Swift tools version 5.9.

```sh
swift test --package-path native
swift build --package-path native -c release
```

To compare Swift and Python results:

```sh
python scripts/parity.py /path/to/GameData/CarModel native/.build/release/nfs5car /path/to/GameData/Track
```

## Publication checks

Before committing or pushing, run:

```sh
python scripts/check_publication.py
```

The checker validates the staged file inventory and catches common accidental
additions. It is not a legal opinion or provenance detector. Review new files before
adding them to the inventory.
