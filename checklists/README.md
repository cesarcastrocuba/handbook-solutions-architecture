# Checklists

## Canonical review checklists (v2.1)

`canonical/<domain>.yaml` is the source of truth for the architecture review checklists (Master Prompt §4.2). Each domain file holds items with stable `SA-<DOMAIN>-NNN` identifiers that do not depend on chapter numbering, plus title, question, rationale, applicability, expected evidence, section, external reference, risk relevance, version and status. Files validate against `schema/review-checklist.schema.json`. Retired identifiers are listed in `retired-ids.txt` and are never reused.

The questions also appear in the manuscript. `python3 scripts/checklists.py --check` keeps the two in step (same text, same order) and fails on missing enrichment; `--export` generates into the ignored `_build/checklists/exports/` directory:

- `_build/checklists/exports/architecture-review-checklist.{csv,json,md}`: consolidated definitions;
- `_build/checklists/exports/architecture-review-assessment-template.csv`: an assessment sheet with blank outcomes (applicable, status, evidence, reviewer, date, findings, remediation owner, due date), kept separate from the definitions.

`make check` runs canonical parity and the reference unit tests in CI.
`make checklist-exports` generates CSV, JSON and Markdown deliverables; they are never committed.
Publishing these files as release assets is hub template gap G6. Never edit exports by hand.

## Historical layers (RC2 evidence)

- **Source transcription layer (`2.0-RC2-source`).** `data/*-source-checklist.yaml` hold the RC2 checklist questions exactly as published, with `CHK-*` IDs, validated against `schema/checklist-source.schema.json` and imported unchanged from the frozen reference. The legacy DOCX inventory/normalization pipeline is not ported. `scripts/export_checklists_csv.py --all` validates these frozen transcriptions against their schema and exports their CSVs plus the enriched pilot and the aggregate in original reading order; canonical definitions are exported separately by `scripts/checklists.py --export`.
- **Enriched pilot layer.** `data/ch06-integration-checklist.yaml` (`schema/checklist.schema.json`, `scripts/export_checklists_csv.py`) is the Phase 1 pilot. The canonical `SA-INT` domain supersedes it.
