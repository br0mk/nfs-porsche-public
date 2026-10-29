# NFS5 data formats

These notes describe observations of the USA 2002 rerelease data. They are not EA
source code. **Observed** means checked against the local reference dataset;
**inferred** means a consistent pattern without an independent reference;
**hypothesis** means a working assumption. Dataset counts below document earlier
local checks, not fixtures supplied with this repository.

Python readers are in `src/nfs5/`; their Swift counterparts are in
`native/Sources/NFS5Kit/`. `scripts/parity.py` compares geometry and pixel checksums
when the user supplies a suitable dataset. Previous local checks covered 40 car
models and 15 tracks. No formal clean-room process is claimed.

## RefPack (QFS) — observed

The header starts with `u8 flags, 0xFB`. If `flags & 1` is set, skip the compressed
size. The uncompressed size follows as three big-endian bytes, or four when
`flags & 0x80` is set; the optional compressed size uses the same width.

LZ77 commands have two, three, or four bytes and combine literals with a back
reference. `0xE0..0xFB` emits `((b & 0x1F) + 1) * 4` literals. `0xFC..0xFF`
terminates the stream after zero to three literals. Overlapping copies are allowed.
The 40 car containers in the reference dataset decoded to their declared lengths.

## FSH / SHPI — observed

Earlier local coverage: 545 files containing 10,127 images.

Header: `"SHPI", u32 size, u32 entry_count, four-byte directory_id` (often `GIMX`).
Directory entries are `(four-byte name, u32 offset)`. Each entry is a chain of
blocks with a 16-byte header:

```text
u8 code, u24 next_block_offset (0 = last)
u16 width, u16 height, u16 centre_x, u16 centre_y, u16 x, u16 y
```

`x` and `y` locate the image on an atlas page.

| Code | Format |
| --- | --- |
| `0x7B` | 8-bit palette indices |
| `0x7D` | ARGB8888, stored as BGRA |
| `0x7F` | RGB888, stored as BGR |
| `0x78` | RGB565 |
| `0x7E` | ARGB1555 |
| `0x6D` | ARGB4444 |
| `0x60`, `0x61` | DXT1, DXT3 (Python decoder) |
| `0x2A` / `0x22`, `0x29`, `0x2D`, `0x24` | Palette: BGRA8888, RGB565, ARGB1555, BGR888 |
| High bit set on image code | RefPack-compressed pixel data |

Interpreting palette code `0x29` as RGB565 is inferred from its size and visual
results. Text and miscellaneous blocks such as `0x6F` and `0x7C` are not decoded.
Python and Swift do not necessarily support every same image code.

## CRP car models — observed on 40 models

Containers may be RefPack-compressed. Four-character tags are byte-reversed:
`" raC"` represents `"Car "`. Directory offsets are relative to the entry itself.

The 16-byte header is `tag, u32 info, u32 misc_count, u32 unknown`, where
`info = (article_count << 5) | flags` and observed car flags include `0x1A`.

An `Arti` entry contains `tag, u32 info, u32 part_count, u32 offset_in_16_byte_units`.
A part entry is `u16 index, two-byte tag, u32 info, u32 count, u32 offset`;
its byte length is `info >> 8`. Miscellaneous entries with four-character tags
have no separate index.

| Tag | Contents |
| --- | --- |
| `Name` | Part name, such as `Body`, `WheelFront`, or `Interior` |
| `Base` | Auxiliary data and a trailing LOD table; incompletely understood |
| `vt`, `nm` | Vertices and normals: four float32 values, with `w = 1` or `0` |
| `df` | Four-byte BGRA colour per triangle corner, used by tracks |
| `uv` | Two float32 texture coordinates, origin at top left |
| `tr` | 4×4 float32 row-vector matrix, translation in the last row |
| `pr` | One material and indexed geometry |
| `$n` | 16 bytes per triangle; meaning unknown |
| `dz`, `ef` | Damage/effect data; not decoded |
| Misc `mt` | Car material, 312 bytes: class name at 16, texture page at 40 |
| Misc `sf` | Embedded SHPI archive; index is the `.tpg` file number minus one |
| Misc `BndP`, `RMth`, `Wndo` | Not decoded |

The low nibble of a part index selects the stream group; for `vt` and `nm`, the
next nibble selects deformation state (`0` means undamaged). The high nibble of a
16-bit `pr` index selects LOD; `1` is the highest-detail car LOD.

A primitive starts with flags, material (bit 31 set), four float32 bounds values
(a sphere is a hypothesis), 16 zero bytes, stream count, and index-stream count.
Each stream record is:

```text
u32 id, u32 byte_offset, u16 byte_length, u16 kind, u16 group, u16 unknown
```

Kinds are `0 = vt`, `1 = nm`, `2 = uv`, `3 = df`, and `0x246E = $n`. Index streams
are `(u16 group, "Iv"/"Iu", u32 offset)` followed by byte indices. Positions and UVs
have separate indices; an absent index stream means sequential access.

The low byte of the flags selects topology: `3` is a triangle list, `4` is a strip,
and `1` is treated as a strip based on observed results. Degenerate strip triangles
are omitted. Stream kinds were resolved using track data, which lacks normals.

Coordinates are left-handed, with +Y upward and the car facing −Z. Export negates
Z and reverses triangle winding to produce a right-handed scene.

## Tracks — observed on 15 tracks

`GameData/Track/<name>.crp` uses the same container with the `Trak` tag, accompanied
by `<name>.fsh`. Parts represent road and scenery. Track LOD `0` is highest detail.
Objects are placed with their `tr` matrices. Coordinates appear to be metres.
The reference `alps` container has 1,752 articles and 286 miscellaneous entries,
with approximate bounds of 1.7 × 6.2 km.

- Lighting is stored in `df` as BGRA. Treating `0x80` as neutral and applying ×2
  modulation is an inference, not an exact reproduction of the original renderer.
- Track materials are 76 bytes. The class name begins at offset 16. Offset 38 holds
  `ns`, a reference to the miscellaneous `sn` filename; offset 40 holds the four-byte
  FSH image name. `FakeSort` is treated as blended, and other transparent images as
  alpha-tested. This is a rendering hypothesis.
- `SimD` road nodes are 80 bytes: flags, position[3], up[3], forward[3], right[3],
  three unused floats, and four widths. The exact meaning of the widths is unresolved.
- `SimT` contains consecutive chain lengths. The longest chain is used as the main
  road. Reference `alps` lengths are 1795, 272, 22, and 16, totalling 2105 nodes.
- `.edg`, `.env`, `.map`, `.jnc`, `.dtx`, `.key`, `.scn`, sky data, and miscellaneous
  camera records are outside this reader's supported scope. A small number of faces
  refer to missing texture entries.

## TPG / CLR — INI-like text

A `.tpg` maps `fileN=<name>.fsh` to `[fileN.details] tpage=K`. A `global=K` entry
selects a shared archive: Shadow, INTGLASS, Suit, Head, or Cabrio for values 1–5.

`[tpageK.details] sourcetpage=M` selects an atlas for the mirrored half of a car.
Each image is flipped horizontally in place, rather than flipping the entire atlas.
Image variants may occupy the same rectangle. The viewer prefers `whg` and `top`;
this is an approximation rather than the original game's selection logic.

A `.clr` contains `[sectionN] colorK.r/g/b/h/s/v` colour schemes. Exterior texels
with alpha below 255 are multiplied by the chosen paint colour. Treating opaque
texels as unpainted lights/badges is a visually plausible hypothesis.

## SIM — car parameters

The observed files are 328 bytes: a 64-byte title followed by 66 four-byte fields.
Initial meanings were inferred from 86 files and compared with menu specification
cards; later binary analysis refined several field meanings. The parser reads
fields, not reconstructed game physics.

| Offset | Meaning | Evidence / limitation |
| --- | --- | --- |
| 64 | Mass, kg | Inferred; often card weight plus roughly 40 kg |
| 68 | Wheelbase, mm | Broad agreement with specification cards |
| 72 | Engine layout: rear/mid/front = 0/1/2 | Observed |
| 76 | Turbo flag | Observed against car names |
| 80 | Forward gear count | Observed |
| 88 | Drive percentage | Binary-analysis interpretation |
| 92 | Front drive percentage | Inferred and informed by binary analysis |
| 96, 100 | Reverse and neutral ratios | Neutral interpretation is inferred |
| 104–124 | Forward ratios 1–6 | Broad agreement with specification cards |
| 128 | Final-drive ratio | Agreement with specification cards |
| 132, 136, 140 | Tyre width, aspect ratio, rim diameter | Binary-analysis interpretation |
| 144 | Top speed, mph | Broad agreement with specification cards |
| 148 | Redline, rpm | Broad agreement with specification cards |
| 156–236 | Torque curve, **21 float32 samples** in lb-ft | Refined by binary analysis; 500 rpm spacing |

Earlier notes described 17 torque samples; the implementation now reads 21.
Occasional disagreement with specification cards may reflect game tuning. Fields
with uncertain meanings remain named `unknown_*`; unnamed offsets are preserved.

## LOC — string tables

The header is `"LOCH", u32 header_size, u32 unknown, u32 block_count`, followed by
block offsets. `LOCI` maps string IDs to indices; `LOCL` stores language strings.
A language block contains `u32 size, u32 zero, u32 count`, offsets relative to the
`LOCL` tag, and NUL-terminated strings. The Python reader uses Latin-1.

Car specification cards use 45 fixed string positions, mapped in `nfs5.loc.CAR_CARD`.
Swift includes a front-end string-table reader and INI-style menu layout reader.
Neither game strings nor layout files are distributed in this repository.
