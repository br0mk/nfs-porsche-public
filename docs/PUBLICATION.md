# Publication scope and provenance review

Review date: 2026-10-29.

## Included material

The release includes the project's Python format readers and exporters, their Swift
counterparts, test code, and factual format documentation.
The selected files are implementations of data parsing, geometry conversion, and
format conversion. They do not contain the address-by-address C translations of the
original executable used by the separate research project.

Some field interpretations were informed by binary analysis as well as data
observation. In particular, the SIM torque curve has 21 points. This repository
makes **no formal clean-room provenance claim**. Inspecting source and local project
history cannot prove that no unidentified third-party expression was ever used.

The root MIT license applies only to rights the contributors can grant in the
included project material. It is not a license from Electronic Arts, Porsche,
Microsoft, Apple, or any dependency author. Dependency licenses remain separate.

## Excluded material

The following are deliberately absent, including from this repository's history:

- Original or modified EXE/DLL files, disc images, patches, cracks, and DRM components.
- Decompiled or manually reconstructed game functions and generated translations.
- Embedded executable/data images, machine-code dumps, recorded memory, and replay states.
- Models, textures, sound, music, video, fonts, game interface art, and game-derived icons.
- Exported glTF/OBJ files, screenshots, game-specific generated datasets, and test fixtures copied from the game.
- Private research logs, analysis evidence, executable function inventories, restore queues,
  old dashboards, and development history.
- Downloaded toolchains, SDKs, dependency source, installed packages, and build products.

The native game host, recompiler, and platform-specific PS4/web game ports are not
part of this release. Their omission is a conservative scope decision, not a finding
that every independent tool in those components is infringing.

## Why choosing a license is not enough

An MIT notice cannot grant third-party rights the contributor does not own. A source
translation of someone else's executable is not made independently licensable merely
by changing its language or excluding the original executable. Copyright protection
covers program expression; the distinction between expression, functional behavior,
and interoperability exceptions depends on facts and jurisdiction.

Sources for the review:

- [U.S. Copyright Office: computer programs](https://www.copyright.gov/register/tx-programs.html)
  distinguishes protected expression from ideas, algorithms, and methods.
- [U.S. Copyright Office: exclusive rights and derivative works](https://www.copyright.gov/title17/92chap1.html)
  describes relevant rights; this is not a conclusion about a particular user's jurisdiction.
- [MIT license terms](https://choosealicense.com/licenses/mit/)
  require preservation of copyright and permission notices and disclaim warranties.

The exact license accompanying the user's game copy and all applicable exceptions
have not been resolved by this repository review. A current EULA for a different EA
product would not establish the terms governing a 2000 game. No blanket assurance
of non-infringement, patent clearance, or freedom from trademark claims is made.

## Release boundary

This is a fresh source-only repository. It has no parent commits or Git object
alternates pointing to the research repository. A single initial commit contains
the reviewed snapshot, so excluded research material cannot be recovered from an
older commit in this repository.

Do not make the full research repository public in place of this export. Do not
attach game data, generated exports, screenshots, or bundled game builds to releases.
The publication checker catches common accidental additions; it cannot replace
source review or establish legal ownership. A qualified legal review is required
if a legally assured release is necessary.
