# Project status

**This file is the single source of current status for this book.** Decisions live only in
[`DECISIONS.md`](DECISIONS.md).

**Updated:** 2026-11-16
**State:** All manuscript sources imported. The platform edition contains all 33 manuscript files
and 121 figures from the frozen reference `v3.0.0` (`13d295b`): front matter, Chapters 1–18,
Appendices A–J, Conclusions and References. Generated sections and book-owned tooling remain pending.

| Item | State |
| --- | --- |
| Content source | Private reference `solutions-architecture-handbook`, tag `v3.0.0`, commit `13d295b` (`DEC-001`) |
| Imported slices | Slices 1–6: front matter; Chapters 1–18; Appendices A–J; Conclusions; References (`DEC-004`) |
| Figures | All 121 rendered PNGs and 121 DOT sources copied byte-for-byte from the frozen source |
| Generated sections | Analytic Index and glossary definition pointers pending platform support; catalog appendices H–J are frozen source snapshots, with regeneration checks pending |
| Book-owned tooling | Catalog/checklist/diagram checks, checklist data and index vocabulary pending the separate tooling PR |
| Canonical pins | Toolkit `0.11.0`, standard profile `1.0.0`; profile `1.1.0` is used only in scratch verification until the coordinated upgrade |
| Releases | None. Next planned: `v3.1.0-rc.1` with the Owner's tag approval (`DEC-005`, `DEC-010`); the complete edition still requires generated-section parity |
| Catalog | Not listed; only `v3.1.0` will be listed |
| Reading site | Pages source set to GitHub Actions; not deployed |

## Next actions

1. Separate tooling PR: catalog generators, checklist parity and exports, diagram checks, and index vocabulary.
2. Restore the analytic Index, glossary pointers and cross-reference links, and close numbering gaps in the hub.
3. Complete publication parity and the Owner's desktop Word check before any tag.
