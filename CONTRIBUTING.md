# Contributing

Submit only code and documentation you have the right to distribute under the
project's MIT license. Identify third-party sources and preserve their notices.
Do not submit reconstructed executable functions, game assets, recorded memory,
private data, or generated game outputs, even as test fixtures.

Use synthetic test inputs created specifically for the test. Keep tests that need
locally supplied game data optional. Do not claim that skipping those tests verifies
compatibility. Report parsing assumptions and unknown fields explicitly.

Run `python -m pytest -q`, `python scripts/check_publication.py`, and, for Swift
changes on macOS, `swift test --package-path native`. Review new files before updating
`publication-files.txt`. Never add an entire research directory to that inventory.
