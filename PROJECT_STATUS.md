# Project status

**This file is the single source of current status for this book.** Decisions live only in
[`DECISIONS.md`](DECISIONS.md).

**Updated:** 2026-11-21
**State:** All manuscript sources imported, Chapter 9 *Platform Architecture* added (DEC-020, now Chapter 17), the table of contents reordered for edition `5.0.0` (DEC-024), and the chapters renumbered for edition `6.0.0` (DEC-025). The platform edition contains 34 manuscript files
and 131 figures: the 33 files and 120 of the 121 figures of the frozen reference `v3.0.0` (`13d295b`) — front matter, the former Chapters 1–18,
Appendices A–J, Conclusions and References, in the edition `6.0.0` order (DEC-020, DEC-024 and DEC-025) — plus the platform chapter and its 11 figures; the former Figure 8.4 was removed with the former section 8.4 of the `4.0.0` numbering; the `6.0.0` renumbering added or removed no figure. Generated sections come from the toolkit (cross-reference links, glossary pointers and the analytic Index, DEC-013); book-owned generators and checks are imported. Document Control states Version `6.0`, Status `Released`, with the rows `3.1 RC1`, `3.1` (DEC-017), `3.1.1` (DEC-019), `4.0` (DEC-021), `5.0` (DEC-024) and `6.0` (DEC-025), and no longer carries the completed Planned Revisions table (DEC-014). Toolkit 0.14.0 supplies the edition layout: literal appendix labels, one validated Document Control table, page-sized tables kept with their captions and lead-ins, natural figure sizes, qpdf PDF compaction and numbered PDF bookmarks (DEC-015); white-backed raster figures are staged transparent for PDF and Word, so they blend with the page instead of showing a white box, while HTML keeps the original PNG (DEC-016). Toolkit 0.14.1 makes those PNGs blend with the light page and read as light lines on the dark page, and keeps the page in place when the theme changes (DEC-019). Toolkit 0.14.2 keeps headings and short introductions with the table, figure or heading after them in desktop Word, and links a location that follows another location in a sentence (DEC-023).

| Item | State |
| --- | --- |
| Content source | Private reference `solutions-architecture-handbook`, tag `v3.0.0`, commit `13d295b` (`DEC-001`) |
| Imported slices | Slices 1–6: front matter; Chapters 1–18 (renumbered by DEC-020, DEC-024 and DEC-025; edition `6.0.0` order); Appendices A–J; Conclusions; References (`DEC-004`) |
| Figures | 120 of the 121 rendered PNGs and DOT sources of the frozen source (`ch08-platform-path` removed with the former section 8.4 of the `4.0.0` numbering, DEC-024), byte-for-byte except `ch12-test-environment-flow` (its section reference renumbered, DEC-020), plus 11 `platform-*` figures for the platform chapter (Chapter 9 in `4.0.0`, Chapter 12 in `5.0.0`, Chapter 17 since `6.0.0`) |
| Generated sections | Cross-reference links, glossary definition pointers and the analytic Index are built by the toolkit (DEC-013); page-sized tables stay with their captions and lead-ins, figures keep their natural size and blend with the page in PDF and Word (DEC-016), and the release PDF is compacted with qpdf (DEC-015); catalog appendices H–J are frozen source snapshots, with regeneration checks passing; checklist exports ship as `book-extras.zip` through `make release-assets` |
| Book-owned tooling | Catalog regeneration, canonical checklist parity, portable diagram-manifest checks and the float-spacing check (DEC-022) run in `make check`; reference tests and checklist data imported; `release-assets` Makefile target stages checklist exports for release packaging; analytic index vocabulary staged as data for hub change 0053 |
| Canonical pins | Toolkit `0.14.2` (hub commit `47c37e23819abb801b1c8635401d6b64e7e14fad`), standard profile `1.1.0` (DEC-012, DEC-013, DEC-015, DEC-016, DEC-019, DEC-023); the release workflow accepts `X.Y.Z-rc.N` pre-releases and requires a compacted PDF |
| Releases | `v3.1.0-rc.1` (pre-release), `v3.1.0` (first complete edition, release run 44323321913 from `b50911e`), `v3.1.1` (DEC-019, release run 44477761172 from `ed4d86b`), `v4.0.0` (Chapter 9, DEC-020 to DEC-023; release run 44767230955 from `1278780`, after the Owner's desktop Word check and tag approval on 2026-11-20) and `v5.0.0` (table of contents reordered, DEC-024; release run 44836848739 from `edfb166`, after the Owner's desktop Word check and tag approval on 2026-11-20) published; `v5.0.0` is the latest |
| Catalog | `v5.0.0` listed in the hub catalog with its author (hub PR 128; `v4.0.0` was listed by hub PR 125, `v3.1.1` by hub PR 116, `HUB-DEC-043`) and shown on the portal |
| Reading site | Live at https://cesarcastrocuba.github.io/handbook-solutions-architecture/, serving `v5.0.0` |

## Next actions

1. Publish checklist exports as release assets; the `release-assets` Makefile target copies generated exports to `$(RELEASE_ASSETS_DIR)`. Gap G6 closes once a template that ships hub change 0057 is released.
2. Restore the analytic Index, glossary pointers and cross-reference links, and close numbering gaps in the hub.
3. Desktop Word check of the `6.0.0` DOCX and Owner approval of the tag `v6.0.0` (DEC-025); then the release and the hub catalog move.

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
