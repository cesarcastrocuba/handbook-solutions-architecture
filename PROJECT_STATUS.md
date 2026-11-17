# Project status

**This file is the single source of current status for this book.** Decisions live only in
[`DECISIONS.md`](DECISIONS.md).

**Updated:** 2026-11-17
**State:** All manuscript sources imported. The platform edition contains all 33 manuscript files
and 121 figures from the frozen reference `v3.0.0` (`13d295b`): front matter, Chapters 1–18,
Appendices A–J, Conclusions and References. Generated sections come from the toolkit (cross-reference links, glossary pointers and the analytic Index, DEC-013); book-owned generators and checks are imported. Document Control states the platform pre-release as `3.1 RC1` and no longer carries the completed Planned Revisions table (DEC-014). Toolkit 0.14.0 supplies the edition layout: literal appendix labels, one validated Document Control table, page-sized tables kept with their captions and lead-ins, natural figure sizes, qpdf PDF compaction and numbered PDF bookmarks (DEC-015).

| Item | State |
| --- | --- |
| Content source | Private reference `solutions-architecture-handbook`, tag `v3.0.0`, commit `13d295b` (`DEC-001`) |
| Imported slices | Slices 1–6: front matter; Chapters 1–18; Appendices A–J; Conclusions; References (`DEC-004`) |
| Figures | All 121 rendered PNGs and 121 DOT sources copied byte-for-byte from the frozen source |
| Generated sections | Cross-reference links, glossary definition pointers and the analytic Index are built by toolkit 0.14.0 (DEC-013); page-sized tables stay with their captions and lead-ins, figures keep their natural size, and the release PDF is compacted with qpdf (DEC-015); catalog appendices H–J are frozen source snapshots, with regeneration checks passing; checklist exports ship as `book-extras.zip` through `make release-assets` |
| Book-owned tooling | Catalog regeneration, canonical checklist parity and portable diagram-manifest checks run in `make check`; reference tests and checklist data imported; `release-assets` Makefile target stages checklist exports for release packaging; analytic index vocabulary staged as data for hub change 0053 |
| Canonical pins | Toolkit `0.14.0` (hub commit `80b833875bce2018b6c15a2ee0acc4726b659175`), standard profile `1.1.0` (DEC-012, DEC-013, DEC-015); the release workflow accepts `X.Y.Z-rc.N` pre-releases and requires a compacted PDF |
| Releases | None. Next planned: `v3.1.0-rc.1` with the Owner's tag approval (`DEC-005`, `DEC-010`); the complete edition still requires generated-section parity |
| Catalog | Not listed; only `v3.1.0` will be listed |
| Reading site | Pages source set to GitHub Actions; not deployed |

## Next actions

1. Publish checklist exports as release assets; the `release-assets` Makefile target copies generated exports to `$(RELEASE_ASSETS_DIR)`. Gap G6 closes once a template that ships hub change 0057 is released.
2. Restore the analytic Index, glossary pointers and cross-reference links, and close numbering gaps in the hub.
3. Complete publication parity and the Owner's desktop Word check before any tag.

## Book tooling boundaries

The frozen generators, tests, checklist schemas/data, diagram manifest, pattern catalog and index
vocabulary are imported from `13d295b`. The checklist parser reads the approved callout title
attribute. Graphviz rendering is optional; CI checks exact source/render sets and all manifest hashes
without rendering. RC4-history and legacy build-sizing tests are retained with explicit dependency
skips: the book does not carry the RC4 tag or the old build module. The current toolkit owns edition
layout; the old effective-print-size assertions are not evidence about the platform edition.

Not ported: `build_book.py`, `docx_postprocess.py`, `reference_docx.py`, `check_docx.py`,
`check_crossrefs.py`, `check_links.py` and `check_structure.py` (shared toolkit responsibilities);
`rc2_*` and `verify_rc2_parity.py` (legacy inventory/normalization); `artifact_optimize.py`
(lossless size optimization and PDF compaction are in toolkit 0.14.0, on by default). Source transcription data remain frozen;
source provenance is preserved rather than regenerated from the legacy DOCX. Generated exports are
not source files and are not committed (HUB-DEC-003).

The historical `--all` exporter validates and exports the imported source transcriptions and the
enriched Chapter 6 pilot from frozen YAML data, including the aggregate in original reading order.
Chapter 6's source IDs come from its explicit DOCX title/question range; a range/count mismatch
fails rather than guessing provenance. Generated exports match the frozen reference bytes.
The canonical CSV/JSON/Markdown exports include all 145 active items.
