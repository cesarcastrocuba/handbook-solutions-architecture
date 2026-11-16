# Solutions Architecture Handbook

A vendor-neutral, practical handbook for designing, evaluating, documenting and governing software
and solution architectures.

This is the platform edition of the handbook, built with the
[Handbook Hub](https://github.com/cesarcastrocuba/handbooks-hub) toolkit `0.13.0` and the standard
profile `1.1.0`. It was created from the hub template `template-v1.6.0`, and its content is being
imported in slices from the author's frozen reference edition `v3.0.0` (see
[`DECISIONS.md`](DECISIONS.md), `DEC-001`).

Status: [`PROJECT_STATUS.md`](PROJECT_STATUS.md) · Decisions: [`DECISIONS.md`](DECISIONS.md) ·
Contributing: [`AGENTS.md`](AGENTS.md) · Licensing: [`NOTICE.md`](NOTICE.md)

## Repository layout

| Path | Purpose |
| --- | --- |
| `book.yaml` | Book descriptor, exact toolkit and profile pins, licenses and catalog metadata |
| `manuscript/book.yml` | Reading order |
| `manuscript/` | Canonical Quarto sources |
| `publishing/_quarto.yml` | Quarto project configuration for HTML, Typst/PDF and DOCX |
| `publishing/metadata.yaml` | Edition version and status consumed by the build |
| `Makefile` | `check`, `book-checks`, `checklist-exports`, `release-assets`, `build` and `full` targets |
| `scripts/`, `checklists/` | Book-owned generators, tests and canonical checklist definitions |
| `.github/workflows/` | `ci.yml` (fast checks), `release.yml` (guarded release and Pages), `initialize-book.yml` (one-time identity rewrite, already run) |

## Checks

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
make check TOOLKIT=.venv/bin/handbook-toolkit PYTHON=.venv/bin/python
# Includes book-owned freshness/parity checks and unit tests, descriptor and cross-references.
make checklist-exports PYTHON=.venv/bin/python  # generated files in _build/checklists/exports/
make release-assets RELEASE_ASSETS_DIR=/path/to/assets PYTHON=.venv/bin/python  # copies checklist exports to release dir
make full TOOLKIT=.venv/bin/handbook-toolkit PYTHON=.venv/bin/python
# Full also builds the edition (Quarto 1.11.9, pdfinfo).
```

Diagram rendering is optional (`python scripts/render_diagrams.py`, requires Graphviz);
`make check` verifies the frozen render manifest without rerendering. See
[`checklists/README.md`](checklists/README.md) for canonical and historical data layers.

Content is licensed under CC BY-SA 4.0 ([`LICENSE`](LICENSE)); build configuration and scripts
under MIT ([`LICENSE-CODE`](LICENSE-CODE)).
