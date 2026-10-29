# Release status

Prepared on 2026-11-02 as a standalone source-only snapshot of the main project's
format readers, exporters, and tests. The game port and graphical viewers are excluded.

## Validation

- Python: 14 synthetic tests passed; 21 local-data integration tests skipped because
  game files are intentionally absent from this repository.
- Swift/macOS: the format library, command-line tool, and test target built;
  1 synthetic test passed and 2 local-data tests skipped before the viewer was removed.
- Markdown documentation is in English; explanatory source comments are in Russian.
  Python docstrings remain English API documentation. Command examples, API names,
  and format identifiers retain their original spelling.

These checks do not verify original game behavior or establish legal clearance. See
`docs/PUBLICATION.md` for the scope and limitations of the review.

## Reproduce the checks

```sh
python -m pytest -q
swift test --package-path native
python scripts/check_publication.py
```

Keep user-supplied game data and generated outputs outside the published snapshot.
Review new files and dependency notices before expanding the release.
