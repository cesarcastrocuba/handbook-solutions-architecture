# Project status

**This file is the single source of current status for this book.** Decisions live only in
[`DECISIONS.md`](DECISIONS.md).

**Updated:** 2026-11-20
**State:** All manuscript sources imported, and Chapter 9 *Platform Architecture* added (DEC-020). The platform edition contains 34 manuscript files
and 132 figures: the 33 files and 121 figures of the frozen reference `v3.0.0` (`13d295b`) — front matter, the former Chapters 1–18 (now 1–8 and 10–19),
Appendices A–J, Conclusions and References — plus the new chapter and its 11 figures. Generated sections come from the toolkit (cross-reference links, glossary pointers and the analytic Index, DEC-013); book-owned generators and checks are imported. Document Control states Version `4.0`, Status `Released`, with the rows `3.1 RC1`, `3.1` (DEC-017), `3.1.1` (DEC-019) and `4.0` (DEC-021), and no longer carries the completed Planned Revisions table (DEC-014). Toolkit 0.14.0 supplies the edition layout: literal appendix labels, one validated Document Control table, page-sized tables kept with their captions and lead-ins, natural figure sizes, qpdf PDF compaction and numbered PDF bookmarks (DEC-015); white-backed raster figures are staged transparent for PDF and Word, so they blend with the page instead of showing a white box, while HTML keeps the original PNG (DEC-016). Toolkit 0.14.1 makes those PNGs blend with the light page and read as light lines on the dark page, and keeps the page in place when the theme changes (DEC-019).

| Item | State |
| --- | --- |
| Content source | Private reference `solutions-architecture-handbook`, tag `v3.0.0`, commit `13d295b` (`DEC-001`) |
| Imported slices | Slices 1–6: front matter; Chapters 1–18 (now 1–8 and 10–19, DEC-020); Appendices A–J; Conclusions; References (`DEC-004`) |
| Figures | The 121 rendered PNGs and DOT sources of the frozen source, byte-for-byte except `ch12-test-environment-flow` (its section reference renumbered, DEC-020), plus 11 `platform-*` figures for Chapter 9 |
| Generated sections | Cross-reference links, glossary definition pointers and the analytic Index are built by the toolkit (DEC-013); page-sized tables stay with their captions and lead-ins, figures keep their natural size and blend with the page in PDF and Word (DEC-016), and the release PDF is compacted with qpdf (DEC-015); catalog appendices H–J are frozen source snapshots, with regeneration checks passing; checklist exports ship as `book-extras.zip` through `make release-assets` |
| Book-owned tooling | Catalog regeneration, canonical checklist parity and portable diagram-manifest checks run in `make check`; reference tests and checklist data imported; `release-assets` Makefile target stages checklist exports for release packaging; analytic index vocabulary staged as data for hub change 0053 |
| Canonical pins | Toolkit `0.14.1` (hub commit `9c4355e5174c41dbbaaae7fe6304c247768b69d2`), standard profile `1.1.0` (DEC-012, DEC-013, DEC-015, DEC-016, DEC-019); the release workflow accepts `X.Y.Z-rc.N` pre-releases and requires a compacted PDF |
| Releases | `v3.1.0-rc.1` (pre-release), `v3.1.0` (first complete edition, release run 44323321913 from `b50911e`) and `v3.1.1` (DEC-019, release run 44477761172 from `ed4d86b`) published. The edition with Chapter 9 is prepared as `4.0.0` (DEC-021); its tag and release need the Owner's approval after the desktop Word check (`DEC-005`) |
| Catalog | `v3.1.1` listed in the hub catalog with its author (hub PR 116, `HUB-DEC-043`) and shown on the portal |
| Reading site | Live at https://cesarcastrocuba.github.io/handbook-solutions-architecture/, serving `v3.1.1` |

## Next actions

1. Publish checklist exports as release assets; the `release-assets` Makefile target copies generated exports to `$(RELEASE_ASSETS_DIR)`. Gap G6 closes once a template that ships hub change 0057 is released.
2. Restore the analytic Index, glossary pointers and cross-reference links, and close numbering gaps in the hub.
3. Desktop Word check of the `4.0.0` DOCX and Owner approval of the tag `v4.0.0` (DEC-021); then the release and the hub catalog move.

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
The canonical CSV/JSON/Markdown exports include all 157 active items in 20 domains.
