#!/usr/bin/env python3
"""Renumber the manuscript by position and rewrite every reference with one map.

Edition 5.0.0 reorders the table of contents: chapters move, sections move
inside their chapter, a section and a figure are deleted, appendix letters swap
and appendix sections are renumbered. Numbers are literal in the sources, so the
working tree is expected to hold the NEW structure (reading order, moved and
deleted headings, figures) while still carrying the OLD literal numbers. This
script derives both numberings, builds one old -> new map per kind and rewrites
every reference in one simultaneous pass per file.

Model:

* NEW numbers are positions. ``manuscript/book.yml`` fixes chapter order
  (1..N), the headings inside each chapter fix section order (N.k, N.k.j, ...),
  figures are numbered by position per chapter or appendix, appendix letters
  come from the ``appendices:`` order, and appendix sections restart at 1.
* OLD numbers are the literals in headings, figure alt text and figure ids; the
  OLD table numbers come from --base because tables carry no literal number.
* A reference is rewritten only when the pinned toolkit would treat it as a
  reference (``handbook_toolkit.xref_links``); version-like numbers, units and
  measurements are left alone. A worded cue ("Section 4.9") is always a
  reference, so it is rewritten even where the toolkit's version lookback
  suppresses the link.
* Nothing is written unless the whole run is clean: a reference to a deleted
  target without --alias, a numbering gap, a figure id that disagrees with its
  alt text or a range whose image is not contiguous aborts the run.

Two guards keep the tool honest:

* If the working tree has the same structure as --base, old and new numbering
  coincide and the tool reports no changes (running it on main must do nothing).
* If the tree already carries the target numbers (the run after ``--apply``),
  the tool reports no changes, so it is idempotent. The state is read from the
  literals: a tree whose headings and figure labels still match --base is old,
  a tree whose literals already equal the positional targets is applied.

A table has no literal number, so a run that changes only table numbering has no
anchor for that state test; the tool refuses it instead of guessing.

Generated appendices C, H, I and J belong to ``scripts/checklists.py`` and
``scripts/generate_catalogs.py``; the tool counts them for numbering but never
rewrites them, and prints the regeneration commands.

Usage::

    python3 scripts/renumber.py --base HEAD
    python3 scripts/renumber.py --base b66f50e --alias 2.15=2.13 --apply

Aliases map a target that no longer exists to a surviving one. ``OLD`` and
``NEW`` are written in the OLD numbering whenever they exist there, so aliases
compose with the map; when ``NEW`` does not exist at --base it is read as a
target in the resulting numbering. The kind of a bare alias follows the shape
of ``OLD``: ``G`` is an appendix, ``5`` a chapter, ``2.15`` a section. Prefix
the kind for a table, a figure, or a cross-kind redirect::

    --alias 2.15=2.13                  deleted section merged into 2.13
    --alias table:2.15=table:2.13      deleted table
    --alias figure:8.4=section:9.1     deleted figure, prose points at a section
    --alias appendix:G=appendix:J      appendix letters swapped

Kinds: chapter, section (numeric or appendix section such as B.11), figure,
table, appendix (letter).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

try:
    from handbook_toolkit.xref_links import (
        BARE_CHAPTER_HEADERS,
        REFERENCE,
        _protected_spans,
        _reference_header,
        _section_ok,
        _section_target,
        _visible,
        cells,
    )
except ImportError as exc:  # pragma: no cover - environment failure
    sys.exit(
        'renumber: the pinned toolkit is not installed '
        f'({exc}); run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt'
    )

ROOT = Path(__file__).resolve().parents[1]
READING_ORDER = Path('manuscript/book.yml')
GROUPS = ('front', 'chapters', 'back', 'appendices', 'references')
KINDS = ('chapter', 'section', 'figure', 'table', 'appendix')

HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*$')
CHAPTER_LABEL = re.compile(r'^(\d{1,2})\.\s+(.*)$')
APPENDIX_LABEL = re.compile(r'^Appendix\s+([A-Z])\s*(?:[—–:]|-)\s*(.*)$')
SECTION_LABEL = re.compile(r'^([A-Z]|\d{1,2})((?:\.\d{1,2})+)\s+(.*)$')
ATTRS = re.compile(r'\s*\{([^{}]*)\}\s*$')
UNNUMBERED = re.compile(r'\.unnumbered\b')
IMAGE = re.compile(r'!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]*)\)(?:\{(?P<attrs>[^}]*)\})?')
FIGURE_ALT = re.compile(
    r'^Figure\s+(?P<label>[0-9A-Z]{1,2}(?:\.\d{1,2})+)\s*(?:[—–:]|-)\s*(?P<rest>.*)$', re.I
)
FIGURE_ID = re.compile(r'#fig-(?P<id>[0-9a-z]{1,2}(?:-[0-9]+)+)')
CAPTION = re.compile(r'^(?::|Table:)\s+(.*\S)\s*$')
CAPTION_ATTR = re.compile(r'\s*\{#tbl-[^}]*\}\s*$')
PIPE = re.compile(r'^\s*\|')

KIND_TOKEN = {
    'chapter': re.compile(r'(?<![\w.])(\d{1,2})(?![\w.]|\.\d)'),
    'section': re.compile(r'(?<![\w.])([0-9A-Z]{1,2}(?:\.[0-9]{1,2}){1,3})(?![\w.]|\.\d)'),
    'figure': re.compile(r'(?<![\w.])([0-9A-Z]{1,2}(?:\.[0-9]{1,2}){1,3})(?![\w.]|\.\d)'),
    'table': re.compile(r'(?<![\w.])([0-9A-Z]{1,2}(?:\.[0-9]{1,2}){1,3})(?![\w.]|\.\d)'),
    'appendix': re.compile(r'(?<![\w.])([A-Z])(?![\w.]|\.\d)'),
}
RANGE_SEPARATOR = re.compile(r'^\s*[–—-]\s*$')
BARE_SECTION = re.compile(r'(?<![\w.])(\d{1,2}(?:\.\d{1,2}){1,3})(?![\w.]|\.\d)')
NUMBER_LIST = re.compile(r'^\s*\d{1,2}(?:\s*(?:,|and|–|-|to)\s*\d{1,2})*\s*$')
SECTIONS_RANGE = re.compile(
    r'\bSections?\s+(\d{1,2}(?:\.\d{1,2})+)\s*[–-]\s*(\d{1,2}(?:\.\d{1,2})+)'
)

# appendices produced by scripts/generate_catalogs.py and scripts/checklists.py
GENERATED_PREFIXES = ('appendix-c-', 'appendix-h-', 'appendix-i-', 'appendix-j-')
WORD_FOR_KIND = {
    'chapter': 'Chapter',
    'section': 'Section',
    'figure': 'Figure',
    'table': 'Table',
    'appendix': 'Appendix',
}


class RenumberError(Exception):
    """A condition that aborts the run before anything is written."""


# --------------------------------------------------------------------------- #
# Reading order and source documents
# --------------------------------------------------------------------------- #


def git_text(root: Path, rev: str, rel: str) -> str:
    try:
        result = subprocess.run(
            ['git', '-C', str(root), 'show', f'{rev}:{rel}'],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RenumberError(f'cannot read {rel} at {rev}: {exc.stderr.strip()}') from exc
    return result.stdout


def load_reading_order(text: str, source: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    current = None
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line if line.lstrip().startswith('-') else line.split('#', 1)[0].rstrip()
        if stripped.lstrip().startswith('-'):
            stripped = re.sub(r'\s+#.*$', '', stripped)
        if not stripped.strip():
            continue
        if not stripped[0].isspace() and stripped.rstrip().endswith(':'):
            current = stripped.strip().rstrip(':')
            groups[current] = []
            continue
        match = re.match(r'^\s*-\s*(\S.*\S)\s*$', stripped)
        if not match or current is None:
            raise RenumberError(f'{source}:{number}: cannot parse reading order line {line!r}')
        groups[current].append(match.group(1))
    for group in GROUPS:
        groups.setdefault(group, [])
    return groups


@dataclass
class Heading:
    line: int
    level: int
    start: int
    end: int
    old: str | None
    title: str
    target: str | None = None


@dataclass
class Figure:
    line: int
    label_start: int
    label_end: int
    id_start: int
    id_end: int
    old: str
    title: str
    src: str
    target: str | None = None


@dataclass
class Table:
    line: int
    caption: str
    copy: str
    old: str | None = None
    target: str | None = None


@dataclass
class Document:
    path: str
    group: str
    text: str
    headings: list[Heading] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    label: str | None = None   # old chapter number or old appendix letter
    target: str | None = None  # new chapter number or new appendix letter

    @property
    def numbered(self) -> bool:
        return self.group in ('chapters', 'appendices')

    @property
    def generated(self) -> bool:
        return Path(self.path).name.startswith(GENERATED_PREFIXES)

    @property
    def title(self) -> str:
        return next((heading.title for heading in self.headings if heading.level == 1), '')


def heading_body(rest: str) -> tuple[str, str]:
    attrs = ATTRS.search(rest)
    if attrs:
        return rest[: attrs.start()].strip(), attrs.group(1)
    return rest.strip(), ''


def parse_document(path: str, group: str, text: str) -> Document:
    document = Document(path=path, group=group, text=text)
    previous = ''
    for number, line in enumerate(text.split('\n')):
        heading = HEADING.match(line)
        if heading:
            hashes, rest = heading.group(1), heading.group(2)
            body, attrs = heading_body(rest)
            prefix_end = len(line) - len(rest)
            if len(hashes) == 1:
                appendix = APPENDIX_LABEL.match(body)
                chapter = CHAPTER_LABEL.match(body)
                if appendix:
                    document.label = appendix.group(1)
                    start = prefix_end + len('Appendix ')
                    document.headings.append(
                        Heading(number, 1, start, start + 1, appendix.group(1),
                                appendix.group(2).strip())
                    )
                elif chapter:
                    document.label = chapter.group(1)
                    document.headings.append(
                        Heading(number, 1, prefix_end, prefix_end + len(chapter.group(1)),
                                chapter.group(1), chapter.group(2).strip())
                    )
            elif not UNNUMBERED.search(attrs):
                section = SECTION_LABEL.match(body)
                if section:
                    label = section.group(1) + section.group(2)
                    document.headings.append(
                        Heading(number, len(hashes), prefix_end, prefix_end + len(label),
                                label, section.group(3).strip())
                    )
        for image in IMAGE.finditer(line):
            attrs = image.group('attrs') or ''
            identity = FIGURE_ID.search(attrs)
            alt = FIGURE_ALT.match(image.group('alt').strip())
            if not identity or not alt:
                continue
            document.figures.append(
                Figure(
                    number,
                    image.start('alt') + alt.start('label'),
                    image.start('alt') + alt.end('label'),
                    image.start('attrs') + identity.start('id'),
                    image.start('attrs') + identity.end('id'),
                    alt.group('label'),
                    alt.group('rest').strip(),
                    image.group('src'),
                )
            )
        caption = CAPTION.match(line)
        if caption and previous.lstrip().startswith('|'):
            clean = CAPTION_ATTR.sub('', caption.group(1).strip())
            document.tables.append(
                Table(number, caption.group(1).strip(), re.sub(r'\s+', ' ', clean).strip())
            )
        if line.strip():
            previous = line
    return document


def figure_identity_problems(document: Document) -> list[str]:
    problems = []
    lines = document.text.split('\n')
    for figure in document.figures:
        expected = figure.old.lower().replace('.', '-')
        actual = lines[figure.line][figure.id_start:figure.id_end].lower()
        if expected != actual:
            problems.append(
                f'{document.path}:{figure.line + 1}: figure alt label {figure.old!r} '
                f'disagrees with id #fig-{actual}'
            )
    return problems


def assign_targets(document: Document) -> None:
    """Give every heading, figure and table its positional target label."""
    if not document.numbered:
        return
    base = document.target
    counters = {level: 0 for level in range(2, 7)}
    figures = tables = 0
    for heading in document.headings:
        if heading.level == 1:
            heading.target = base
            continue
        if heading.old is None:
            continue
        if heading.level == 2:
            counters[2] += 1
            for deeper in range(3, 7):
                counters[deeper] = 0
            parts = [counters[2]]
        else:
            counters[heading.level] += 1
            for deeper in range(heading.level + 1, 7):
                counters[deeper] = 0
            parts = [counters[level] for level in range(2, heading.level + 1)]
        heading.target = '.'.join([base, *(str(part) for part in parts)])
    for figure in document.figures:
        figures += 1
        figure.target = f'{base}.{figures}'
    for table in document.tables:
        tables += 1
        table.target = f'{base}.{tables}'


def manuscript_path(entry: str) -> str:
    return str(Path('manuscript') / entry)


def manuscript_files(root: Path) -> tuple[dict[str, list[str]], list[Document]]:
    order_path = root / READING_ORDER
    if not order_path.is_file():
        raise RenumberError(f'missing reading order {READING_ORDER}')
    groups = load_reading_order(order_path.read_text(encoding='utf-8'), str(READING_ORDER))
    documents = []
    for group in GROUPS:
        for entry in groups[group]:
            path = manuscript_path(entry)
            full = root / path
            if not full.is_file():
                raise RenumberError(f'reading order entry does not exist: {path}')
            documents.append(parse_document(path, group, full.read_text(encoding='utf-8')))
    return groups, documents


def base_documents(root: Path, rev: str) -> tuple[dict[str, list[str]], list[Document]]:
    groups = load_reading_order(git_text(root, rev, str(READING_ORDER)), f'{rev}:{READING_ORDER}')
    documents = []
    for group in GROUPS:
        for entry in groups[group]:
            path = manuscript_path(entry)
            documents.append(parse_document(path, group, git_text(root, rev, path)))
    return groups, documents


# --------------------------------------------------------------------------- #
# Numbering plan
# --------------------------------------------------------------------------- #


@dataclass
class Plan:
    chapters: dict[str, str]
    sections: dict[str, str]
    figures: dict[str, str]
    tables: dict[str, str]
    appendices: dict[str, str]
    base_sections: set[str]
    base_figures: set[str]
    base_tables: set[str]
    base_chapters: set[str]
    base_appendices: set[str]
    working: list[Document]
    base_documents: list[Document]
    base_fingerprint: tuple = ()
    work_fingerprint: tuple = ()

    def universe(self, kind: str) -> set[str]:
        return {
            'chapter': self.base_chapters,
            'section': self.base_sections,
            'figure': self.base_figures,
            'table': self.base_tables,
            'appendix': self.base_appendices,
        }[kind]

    def mapping(self, kind: str) -> dict[str, str]:
        return {
            'chapter': self.chapters,
            'section': self.sections,
            'figure': self.figures,
            'table': self.tables,
            'appendix': self.appendices,
        }[kind]

    def identity(self) -> 'Plan':
        """A plan whose maps are the identity of the tree's current labels."""
        chapters = {d.label: d.label for d in self.working
                    if d.group == 'chapters' and d.label}
        appendices = {d.label: d.label for d in self.working
                      if d.group == 'appendices' and d.label}
        sections = {h.old: h.old for d in self.working if d.numbered and not d.generated
                    for h in d.headings if h.level > 1 and h.old}
        figures = {f.old: f.old for d in self.working if d.numbered and not d.generated
                   for f in d.figures}
        tables = {t.target: t.target for d in self.working if d.numbered and not d.generated
                  for t in d.tables}
        return replace(self, chapters=chapters, sections=sections, figures=figures,
                       tables=tables, appendices=appendices)


def structural_fingerprint(groups: dict[str, list[str]], documents: list[Document]) -> tuple:
    by_path = {document.path: document for document in documents}
    signature = []
    for group in GROUPS:
        signature.append((group, tuple(groups[group])))
        for entry in groups[group]:
            document = by_path[manuscript_path(entry)]
            signature.append(
                (
                    document.path,
                    tuple((heading.level, heading.title) for heading in document.headings),
                    tuple((figure.title, figure.src) for figure in document.figures),
                    tuple(table.copy for table in document.tables),
                )
            )
    return tuple(signature)


def label_base_tables(documents: list[Document]) -> set[str]:
    labels = set()
    for document in documents:
        if document.numbered and document.label:
            for position, table in enumerate(document.tables, 1):
                table.old = f'{document.label}.{position}'
                labels.add(table.old)
    return labels


def build_plan(root: Path, rev: str) -> Plan:
    base_groups, base = base_documents(root, rev)
    work_groups, work = manuscript_files(root)

    base_chapters = {document.label: document for document in base
                     if document.group == 'chapters' and document.label}
    base_appendices = {document.label: document for document in base
                       if document.group == 'appendices' and document.label}
    if not base_chapters:
        raise RenumberError(f'no numbered chapters at {rev}')
    base_by_title = {(document.group, document.title): document
                     for document in base if document.numbered and document.label}
    base_tables = label_base_tables(base)

    pairs: list[tuple[str, str, str]] = []
    chapters: dict[str, str] = {}
    appendices: dict[str, str] = {}
    sections: dict[str, str] = {}
    figures: dict[str, str] = {}
    tables: dict[str, str] = {}

    chapter_index = appendix_index = 0
    for document in work:
        if document.group == 'chapters':
            chapter_index += 1
            document.target = str(chapter_index)
            if not document.label:
                raise RenumberError(f'{document.path}: chapter heading has no literal number')
            chapters[document.label] = document.target
            pairs.append(('chapter', document.label, document.path))
        elif document.group == 'appendices':
            if appendix_index >= 26:
                raise RenumberError('more than 26 appendices')
            document.target = chr(ord('A') + appendix_index)
            appendix_index += 1
            if not document.label:
                raise RenumberError(f'{document.path}: appendix heading has no literal letter')
            appendices[document.label] = document.target
            pairs.append(('appendix', document.label, document.path))
        assign_targets(document)
        if not document.numbered or document.generated:
            continue
        for heading in document.headings:
            if heading.level == 1 or heading.old is None or heading.target is None:
                continue
            sections[heading.old] = heading.target
            pairs.append(('section', heading.old, f'{document.path}:{heading.line + 1}'))
        for figure in document.figures:
            figures[figure.old] = figure.target
            pairs.append(('figure', figure.old, f'{document.path}:{figure.line + 1}'))

    # Tables carry no literal number: match working captions against the
    # captions of the chapter or appendix that had the same old label at --base.
    for document in work:
        if not document.numbered or document.generated:
            continue
        # The title survives a move, a rename and a renumbering, so it finds the
        # document that carried this content at --base. The old label is the
        # fallback for a document whose title was edited in the same change.
        source = base_by_title.get((document.group, document.title))
        if source is None:
            source = (base_chapters if document.group == 'chapters'
                      else base_appendices).get(document.label or '')
        if source is None:
            raise RenumberError(
                f'{document.path}: no target numbered {document.label!r} at {rev}'
            )
        base_captions = [table.copy for table in source.tables]
        base_labels = [table.old for table in source.tables]
        used: set[int] = set()
        for table in document.tables:
            candidates = [
                index for index, caption in enumerate(base_captions)
                if caption == table.copy and index not in used
            ]
            if not candidates:
                raise RenumberError(
                    f'{document.path}:{table.line + 1}: table caption not found at {rev}: '
                    f'{table.caption!r}'
                )
            index = candidates[0]
            used.add(index)
            tables[base_labels[index]] = table.target
            pairs.append(('table', base_labels[index], f'{document.path}:{table.line + 1}'))

    problems = []
    seen: dict[tuple[str, str], str] = {}
    for kind, old, where in pairs:
        key = (kind, old)
        if key in seen:
            problems.append(f'duplicate old {kind} number {old}: {seen[key]} and {where}')
        seen[key] = where
    for kind, mapping in (('chapter', chapters), ('appendix', appendices)):
        values = list(mapping.values())
        expected = ([str(index) for index in range(1, len(values) + 1)]
                    if kind == 'chapter'
                    else [chr(ord('A') + index) for index in range(len(values))])
        if sorted(values) != sorted(expected) or len(set(values)) != len(values):
            problems.append(f'{kind} numbering has a gap or duplicate: {values}')
    if problems:
        raise RenumberError('; '.join(problems))

    return Plan(
        chapters=chapters,
        sections=sections,
        figures=figures,
        tables=tables,
        appendices=appendices,
        base_sections={heading.old for document in base if document.numbered
                       for heading in document.headings if heading.level > 1 and heading.old},
        base_figures={figure.old for document in base if document.numbered
                      for figure in document.figures},
        base_tables=base_tables,
        base_chapters=set(base_chapters),
        base_appendices=set(base_appendices),
        working=work,
        base_documents=base,
        base_fingerprint=structural_fingerprint(base_groups, base),
        work_fingerprint=structural_fingerprint(work_groups, work),
    )


def applied_numbering(plan: Plan) -> bool:
    """True when the literals already carry the positional targets.

    Titles (not numbers) match a working document to its --base counterpart, so
    a moved chapter, a renamed file or a reordered section still compares the
    same physical heading.
    """
    lookup = {(document.group, document.title): document
              for document in plan.base_documents if document.numbered}
    for document in plan.working:
        if not document.numbered or document.generated:
            continue
        source = lookup.get((document.group, document.title))
        if source is None:
            continue
        if document.label != source.label:
            return True
        olds: dict[str, list[str]] = {}
        for heading in source.headings:
            if heading.level > 1 and heading.old:
                olds.setdefault(heading.title, []).append(heading.old)
        for heading in document.headings:
            if heading.level == 1 or not heading.old:
                continue
            queue = olds.get(heading.title)
            if queue and heading.old != queue.pop(0):
                return True
        figures: dict[str, list[str]] = {}
        for figure in source.figures:
            figures.setdefault(figure.title, []).append(figure.old)
        for figure in document.figures:
            queue = figures.get(figure.title)
            if queue and figure.old != queue.pop(0):
                return True
    return False


# --------------------------------------------------------------------------- #
# Aliases
# --------------------------------------------------------------------------- #


ALIAS_KIND = re.compile(r'^(chapter|section|figure|table|appendix):(.+)$')


def split_kind(value: str) -> tuple[str | None, str]:
    match = ALIAS_KIND.match(value.strip())
    if match:
        return match.group(1), match.group(2).strip()
    return None, value.strip()


def shape_kind(value: str) -> str | None:
    """The kind a written target shape implies: 2.15 section, G appendix, 5 chapter."""
    if re.fullmatch(r'[A-Z]', value):
        return 'appendix'
    if re.fullmatch(r'[A-Z](?:\.\d{1,2})+', value):
        return 'section'
    if re.fullmatch(r'\d{1,2}', value):
        return 'chapter'
    if re.fullmatch(r'\d{1,2}(?:\.\d{1,2})+', value):
        return 'section'
    return None


def new_universe(plan: Plan, kind: str) -> set[str]:
    values = set(plan.mapping(kind).values())
    for document in plan.working:
        if document.numbered:
            for heading in document.headings:
                if heading.target and heading.level > 1:
                    values.add(heading.target)
    return values


def resolve_target(plan: Plan, kind: str, new: str) -> str | None:
    if new in plan.mapping(kind):
        return plan.mapping(kind)[new]
    if new in new_universe(plan, kind):
        return new
    return None


def build_aliases(plan: Plan, values: list[str]) -> dict[tuple[str, str], tuple[str, str]]:
    aliases: dict[tuple[str, str], tuple[str, str]] = {}
    for value in values:
        if '=' not in value:
            raise RenumberError(f'alias {value!r} is not OLD=NEW')
        left, right = value.split('=', 1)
        old_kind, old = split_kind(left)
        new_kind, new = split_kind(right)
        if old_kind is None:
            old_kind = shape_kind(old)
            if old_kind is None:
                raise RenumberError(
                    f'alias {value!r}: cannot tell which kind {old!r} is; prefix it '
                    '(chapter, section, figure, table, appendix)')
            if old not in plan.universe(old_kind):
                raise RenumberError(
                    f'alias {value!r}: {old!r} is not a {old_kind} at --base; '
                    f'prefix the kind if it belongs to another one')
        kinds = [old_kind]
        for kind in kinds:
            if old in plan.mapping(kind):
                raise RenumberError(
                    f'alias {value!r}: {old!r} still exists in the new tree; nothing to alias'
                )
            target_kind = new_kind or kind
            target = resolve_target(plan, target_kind, new)
            if target is None:
                raise RenumberError(
                    f'alias {value!r}: target {new!r} is not a {target_kind} in the new tree'
                )
            aliases[(kind, old)] = (target_kind, target)
    return aliases


# --------------------------------------------------------------------------- #
# Rewriting
# --------------------------------------------------------------------------- #


@dataclass
class Report:
    changes: list[tuple[str, int, str]] = field(default_factory=list)
    suspicious: list[tuple[str, int, str, str]] = field(default_factory=list)
    bare_cells: list[tuple[str, int, str]] = field(default_factory=list)
    manual: list[tuple[str, int, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    missing: set[tuple[str, str]] = field(default_factory=set)
    dot: list[tuple[str, int, str]] = field(default_factory=list)


def contiguous(kind: str, first: str, second: str) -> bool:
    """True when the second label immediately follows the first."""
    if kind == 'appendix':
        return len(first) == len(second) == 1 and ord(second) - ord(first) == 1
    if kind == 'chapter':
        return first.isdigit() and second.isdigit() and int(second) - int(first) == 1
    head = first.rsplit('.', 1)
    tail = second.rsplit('.', 1)
    if len(head) == len(tail) == 2 and head[0] == tail[0]:
        return int(tail[1]) - int(head[1]) == 1
    return False


def expand_range(kind: str, first: str, second: str) -> list[str] | None:
    """Every label from first to second, or None when the range is malformed."""
    if kind == 'appendix':
        if len(first) != 1 or len(second) != 1:
            return None
        start, end = ord(first), ord(second)
        return [chr(value) for value in range(start, end + 1)] if end >= start else None
    if kind == 'chapter':
        if not first.isdigit() or not second.isdigit():
            return None
        start, end = int(first), int(second)
        return [str(value) for value in range(start, end + 1)] if end >= start else None
    first_prefix, _, first_tail = first.rpartition('.')
    second_prefix, _, second_tail = second.rpartition('.')
    if first_prefix != second_prefix or not first_tail.isdigit() or not second_tail.isdigit():
        return None
    start, end = int(first_tail), int(second_tail)
    if end < start:
        return None
    return [f'{first_prefix}.{value}' for value in range(start, end + 1)]


class Rewriter:
    def __init__(self, plan: Plan, aliases: dict[tuple[str, str], tuple[str, str]],
                 report: Report, identity: bool = False):
        self.plan = plan
        self.aliases = aliases
        self.report = report
        self.identity = identity
        self.sections = {_section_target(number): number for number in plan.base_sections}
        self.path = ''
        self.line = 0

    # -- resolution ------------------------------------------------------- #

    def record(self, kind: str, old: str, new: str) -> None:
        self.report.changes.append((self.path, self.line + 1, f'{kind} {old} -> {new}'))

    def resolve(self, kind: str, old: str) -> str | None:
        mapping = self.plan.mapping(kind)
        if old in mapping:
            return mapping[old]
        alias = self.aliases.get((kind, old))
        if alias and alias[0] == kind:
            return alias[1]
        if old in self.plan.universe(kind):
            if (kind, old) not in self.report.missing:
                self.report.missing.add((kind, old))
                hint = (f'; aliased to {alias[0]} {alias[1]}, rewrite by hand'
                        if alias else '; pass --alias to redirect it')
                self.report.errors.append(
                    f'{self.path}:{self.line + 1}: reference to deleted {kind} {old}{hint}'
                )
        return None

    def cross_kind(self, kind: str, old: str) -> tuple[str, str] | None:
        alias = self.aliases.get((kind, old))
        return alias if alias and alias[0] != kind else None

    # -- number lists ------------------------------------------------------ #

    def rewrite_list(self, text: str, kind: str) -> str | None:
        """Replace every token of one kind; None when a range cannot be mapped."""
        matches = list(KIND_TOKEN[kind].finditer(text))
        if not matches:
            return None
        replacements: dict[int, tuple[int, int, str, str]] = {}
        for index, match in enumerate(matches):
            old = match.group(1)
            new = self.resolve(kind, old)
            if new is None:
                continue
            replacements[match.start(1)] = (match.start(1), match.end(1), old, new)
            if index + 1 < len(matches):
                between = text[match.end(): matches[index + 1].start()]
                if RANGE_SEPARATOR.match(between):
                    following = matches[index + 1].group(1)
                    if not self.check_range(kind, old, following):
                        return None
        if not replacements:
            return None
        for start in sorted(replacements, reverse=True):
            begin, end, old, new = replacements[start]
            if old != new:
                self.record(kind, old, new)
            text = text[:begin] + new + text[end:]
        return text

    def check_range(self, kind: str, first: str, second: str) -> bool:
        """Validate a range image; report and refuse a non-contiguous one."""
        labels = expand_range(kind, first, second)
        if labels is None:
            self.failed_range(kind, first, second, 'crosses a numbering boundary')
            return False
        image = []
        for label in labels:
            new = self.plan.mapping(kind).get(label)
            if new is None:
                new = self.resolve(kind, label)
            if new is None:
                return False
            image.append(new)
        # A range is safe when its image is the contiguous span between its own
        # endpoints, in any order: "Chapters 1-19" stays a whole-book range after
        # a permutation, while "13-15" does not survive one. The endpoints are
        # rewritten in place, so a permuted span needs no text edit.
        span = expand_range(kind, image[0], image[-1])
        if span and len(set(image)) == len(image) and set(image) == set(span):
            return True
        self.failed_range(kind, first, second, f'maps to {", ".join(image)}')
        return False

    def failed_range(self, kind: str, first: str, second: str, reason: str) -> None:
        phrase = f'{first}–{second}'
        self.report.manual.append(
            (self.path, self.line + 1,
             f'{kind} {phrase!r} {reason}, not contiguous; rewrite by hand')
        )
        self.report.errors.append(
            f'{self.path}:{self.line + 1}: {kind} range {phrase!r} is not contiguous '
            f'after renumbering ({reason})'
        )

    # -- toolkit reference matches ---------------------------------------- #

    def sections_range_check(self, line: str) -> None:
        for match in SECTIONS_RANGE.finditer(line):
            first, second = match.group(1), match.group(2)
            if first not in self.plan.sections and second not in self.plan.sections:
                continue
            self.check_range('section', first, second)

    def inline_edits(self, text: str, blocked: tuple[tuple[int, int], ...] = (),
                     reference_cell: bool = False) -> list[tuple[int, int, str]]:
        self.sections_range_check(text)
        protected = _protected_spans(text) + list(blocked)
        edits = []
        for match in REFERENCE.finditer(text):
            if any(start < match.end() and match.start() < end for start, end in protected):
                continue
            kind = next(
                (name for name in
                 ('figure', 'fig_short', 'table', 'appendix', 'appendices', 'chapter',
                  'section_cue', 'appendix_section', 'section')
                 if match.group(name)),
                None,
            )
            if kind is None:
                continue
            replacement = self.rewrite_match(match, text, kind, reference_cell)
            if replacement is not None and replacement != match.group(0):
                edits.append((match.start(), match.end(), replacement))
        return edits

    def rewrite_match(self, match: re.Match[str], line: str, kind: str,
                      reference_cell: bool) -> str | None:
        def phrase(group: str, phrase_kind: str, worded: bool) -> str | None:
            return self.rewrite_phrase(
                kind=phrase_kind, numbers=match.group(group), phrase=match.group(0),
                worded=worded, offset=match.start(group) - match.start())

        if kind in ('figure', 'fig_short'):
            group = 'figure_nums' if kind == 'figure' else 'fig_short_nums'
            return phrase(group, 'figure', worded=kind == 'figure')
        if kind == 'table':
            return phrase('table_nums', 'table', worded=True)
        if kind == 'chapter':
            return phrase('chapter_nums', 'chapter', worded=True)
        if kind == 'appendix':
            if '.' in match.group('appendix_num'):
                return phrase('appendix_num', 'section', worded=True)
            return phrase('appendix_num', 'appendix', worded=True)
        if kind == 'appendices':
            return phrase('appendices_nums', 'appendix', worded=True)
        if kind == 'section_cue':
            # A worded cue is a reference even when a version earlier on the line
            # stops the toolkit's own link pass.
            number = match.group('section_cue_num')
            if _section_target(number) not in self.sections:
                return None
            return phrase('section_cue_num', 'section', worded=True)
        if kind == 'appendix_section':
            number = match.group('appendix_section_num')
            if not _section_ok(number, line, match.start(), match.end(), self.sections,
                               reference=reference_cell):
                return None
            return phrase('appendix_section_num', 'section', worded=False)
        number = match.group('section_num')
        if not _section_ok(number, line, match.start(), match.end(), self.sections,
                           reference=reference_cell):
            return None
        return phrase('section_num', 'section', worded=False)

    def rewrite_phrase(self, kind: str, numbers: str, phrase: str, worded: bool,
                       offset: int) -> str | None:
        tokens = list(KIND_TOKEN[kind].finditer(numbers))
        if not tokens:
            return None
        single = len(tokens) == 1 and not RANGE_SEPARATOR.search(numbers[tokens[0].end():])
        if single and worded:
            alias = self.cross_kind(kind, tokens[0].group(1))
            if alias:
                new_kind, new = alias
                self.record(kind, tokens[0].group(1), f'{new_kind} {new}')
                return f'{WORD_FOR_KIND[new_kind]} {new}'
        rewritten = self.rewrite_list(numbers, kind)
        if rewritten is None or rewritten == numbers:
            return None
        return phrase[:offset] + rewritten + phrase[offset + len(numbers):]


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #


def apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def table_header(document: Document, line: int) -> list[str] | None:
    lines = document.text.split('\n')
    index = line - 1
    while index >= 0 and PIPE.match(lines[index]):
        index -= 1
    first = index + 1
    if first == line:
        return None
    return cells(lines[first])


def rewrite_row(document: Document, line_number: int, line: str,
                rewriter: Rewriter) -> tuple[str, bool]:
    header = table_header(document, line_number)
    if header is None:
        return line, False
    row = cells(line)
    changed = False
    for index, cell in enumerate(row):
        name = header[index].strip().lower() if index < len(header) else ''
        stripped = cell.strip()
        reference = _reference_header(name)
        bare_chapters = (name in BARE_CHAPTER_HEADERS and NUMBER_LIST.fullmatch(stripped))
        if bare_chapters:
            rewritten = rewriter.rewrite_list(stripped, 'chapter')
            edits = ([(0, len(cell), rewritten)] if rewritten is not None
                     else rewriter.inline_edits(cell, reference_cell=True))
        else:
            edits = rewriter.inline_edits(cell, reference_cell=reference)
            if not reference and BARE_SECTION.fullmatch(stripped):
                new = rewriter.plan.sections.get(stripped)
                if new and new != stripped:
                    rewriter.report.bare_cells.append(
                        (document.path, line_number + 1, f'{stripped} -> {new}: {stripped!r}')
                    )
        new_cell = apply_edits(cell, edits)
        if new_cell != cell:
            row[index] = new_cell
            changed = True
        suspicious_tokens(cell, [(start, end) for start, end, _ in edits], rewriter, document)
    if not changed:
        return line, False
    return '| ' + ' | '.join(cell.strip() for cell in row) + ' |', True


def suspicious_tokens(text: str, covered: list[tuple[int, int]], rewriter: Rewriter,
                      document: Document) -> None:
    protected = _protected_spans(text)
    for match in BARE_SECTION.finditer(text):
        if any(start < match.end() and match.start() < end for start, end in protected):
            continue
        if any(start < match.end() and match.start() < end for start, end in covered):
            continue
        token = match.group(1)
        old = (rewriter.plan.sections.get(token) or rewriter.plan.figures.get(token)
               or rewriter.plan.tables.get(token))
        if old is None or old == token:
            continue
        context = text[max(0, match.start() - 40): match.end() + 40].replace('\n', ' ')
        rewriter.report.suspicious.append(
            (document.path, rewriter.line + 1, token, context.strip()))
    for match in re.finditer(r'\bChapter\s+(\d{1,2})\b', text):
        if any(start < match.end() and match.start() < end for start, end in protected):
            continue
        if any(start < match.end() and match.start() < end for start, end in covered):
            continue
        new = rewriter.plan.chapters.get(match.group(1))
        if new is None or new == match.group(1):
            continue
        context = text[max(0, match.start() - 40): match.end() + 40].replace('\n', ' ')
        rewriter.report.suspicious.append(
            (document.path, rewriter.line + 1, f'Chapter {match.group(1)}', context.strip()))


def rewrite_document(document: Document, rewriter: Rewriter) -> str:
    rewriter.path = document.path
    visible = _visible(document.text)
    lines = document.text.split('\n')
    headings = {heading.line: heading for heading in document.headings}
    figures = {figure.line: figure for figure in document.figures}
    output = []
    for number, line in enumerate(lines):
        rewriter.line = number
        if number not in visible:
            output.append(line)
            continue
        structural: list[tuple[int, int, str]] = []
        heading = headings.get(number)
        if (not rewriter.identity and heading and heading.old and heading.target
                and heading.old != heading.target):
            rewriter.record('heading', heading.old, heading.target)
            structural.append((heading.start, heading.end, heading.target))
        figure = figures.get(number)
        if not rewriter.identity and figure and figure.target and figure.old != figure.target:
            rewriter.record('figure', figure.old, figure.target)
            structural.append((figure.label_start, figure.label_end, figure.target))
            structural.append(
                (figure.id_start, figure.id_end, figure.target.lower().replace('.', '-')))
        if PIPE.match(line):
            new_line, _ = rewrite_row(document, number, line, rewriter)
        else:
            blocked = tuple((start, end) for start, end, _ in structural)
            edits = structural + rewriter.inline_edits(line, blocked)
            new_line = apply_edits(line, edits)
            suspicious_tokens(line, [(start, end) for start, end, _ in edits],
                              rewriter, document)
        output.append(new_line)
    return '\n'.join(output)


# --------------------------------------------------------------------------- #
# YAML sources
# --------------------------------------------------------------------------- #


SECTION_KEY = re.compile(r"(\bsection:\s*)(['\"]?)([0-9A-Z][0-9A-Z.]*)(\2)(?=[,}\s]|$)")
DEFINED_KEY = re.compile(r"^(\s*defined:\s*)(['\"]?)([0-9A-Z][0-9A-Z.]*)(\2)\s*$")
RATIONALE = re.compile(r'(\bsection\s+)(\d{1,2}(?:\.\d{1,2})+)(\s+owns\b)')


def yaml_targets(root: Path) -> list[Path]:
    files = [root / 'publishing' / 'pattern-catalog.yaml',
             root / 'publishing' / 'index-vocabulary.yaml']
    files += sorted((root / 'checklists' / 'canonical').glob('*.yaml'))
    return [path for path in files if path.is_file()]


def rewrite_yaml(root: Path, rewriter: Rewriter) -> dict[Path, str]:
    changed: dict[Path, str] = {}
    for path in yaml_targets(root):
        rel = str(path.relative_to(root))
        original = path.read_text(encoding='utf-8')
        output = []
        for number, line in enumerate(original.split('\n')):
            rewriter.path = rel
            rewriter.line = number

            def section_value(match: re.Match[str]) -> str:
                old = match.group(3)
                new = rewriter.resolve('section', old)
                if new is None or new == old:
                    return match.group(0)
                rewriter.record('section', old, new)
                return match.group(1) + match.group(2) + new + match.group(4)

            new_line = SECTION_KEY.sub(section_value, line)
            defined = DEFINED_KEY.match(new_line)
            if defined:
                old = defined.group(3)
                new = rewriter.resolve('section', old)
                if new and new != old:
                    rewriter.record('section', old, new)
                    new_line = defined.group(1) + defined.group(2) + new + defined.group(4)

            def rationale(match: re.Match[str]) -> str:
                old = match.group(2)
                new = rewriter.resolve('section', old)
                if new is None or new == old:
                    return match.group(0)
                rewriter.record('section', old, new)
                return match.group(1) + new + match.group(3)

            new_line = RATIONALE.sub(rationale, new_line)
            output.append(new_line)
        text = '\n'.join(output)
        if text != original:
            changed[path] = text
    return changed


def report_diagrams(root: Path, plan: Plan) -> list[tuple[str, int, str]]:
    found = []
    pattern = re.compile(r'(?<![\w.])([0-9A-Z]{1,2}(?:\.\d{1,2}){1,3})(?![\w.]|\.\d)')
    directory = root / 'assets' / 'diagrams' / 'src'
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob('*.dot')):
        rel = str(path.relative_to(root))
        for number, line in enumerate(path.read_text(encoding='utf-8').split('\n'), 1):
            for match in pattern.finditer(line):
                token = match.group(1)
                new = (plan.sections.get(token) or plan.figures.get(token)
                       or plan.tables.get(token))
                if new and new != token:
                    found.append((rel, number, f'{token} -> {new}: {line.strip()[:160]}'))
    return found


# --------------------------------------------------------------------------- #
# State checks
# --------------------------------------------------------------------------- #


def state_notes(plan: Plan, applied: bool) -> list[str]:
    """Problems that mean the tree is neither wholly old nor wholly applied."""
    notes = []
    for document in plan.working:
        if not document.numbered or document.generated:
            continue
        for heading in document.headings:
            if heading.old is None or heading.target is None:
                continue
            if heading.level == 1:
                universe = plan.universe('chapter' if document.group == 'chapters' else 'appendix')
            else:
                universe = plan.base_sections
            if applied and heading.old != heading.target:
                notes.append(f'{document.path}:{heading.line + 1}: {heading.old!r} is not the '
                             f'target {heading.target!r} while other numbers are already applied')
            elif not applied and heading.old not in universe:
                notes.append(f'{document.path}:{heading.line + 1}: {heading.old!r} matches '
                             f'neither --base nor the target {heading.target!r}')
        for figure in document.figures:
            if applied and figure.old != figure.target:
                notes.append(f'{document.path}:{figure.line + 1}: figure {figure.old!r} is not '
                             f'the target {figure.target!r} while other numbers are already applied')
            elif not applied and figure.old not in plan.base_figures:
                notes.append(f'{document.path}:{figure.line + 1}: figure {figure.old!r} matches '
                             f'neither --base nor the target {figure.target!r}')
    return notes


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #


def print_maps(plan: Plan, aliases: dict[tuple[str, str], tuple[str, str]],
               identity: bool) -> None:
    for kind in KINDS:
        mapping = plan.mapping(kind)
        changed = 0 if identity else sum(1 for old, new in mapping.items() if old != new)
        pairs = '  '.join(
            f'{old}\u2192{old if identity else new}' for old, new in mapping.items())
        print(f'MAP {kind} ({len(mapping)} targets, {changed} changed)')
        print(f'  {pairs}' if pairs else '  (none)')
    if aliases:
        print('ALIASES')
        for (kind, old), (new_kind, new) in sorted(aliases.items()):
            print(f'  {kind} {old} -> {new_kind} {new}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Renumber the manuscript by position and rewrite every reference.')
    parser.add_argument('--base', required=True, help='git revision holding the OLD numbering')
    parser.add_argument('--alias', action='append', default=[], metavar='OLD=NEW',
                        help='map a deleted target to a surviving one (repeatable)')
    parser.add_argument('--apply', action='store_true',
                        help='write the files (default: dry run)')
    parser.add_argument('--root', default=str(ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        plan = build_plan(root, args.base)
        aliases = build_aliases(plan, args.alias)
        applied = applied_numbering(plan)
    except RenumberError as exc:
        print(f'renumber: {exc}', file=sys.stderr)
        return 1

    identical_structure = plan.base_fingerprint == plan.work_fingerprint
    identity = identical_structure or applied
    literal_change = any(
        old != new
        for kind in ('chapter', 'section', 'figure', 'appendix')
        for old, new in plan.mapping(kind).items()
    )
    table_change = any(old != new for old, new in plan.tables.items())
    notes = state_notes(plan, applied)
    if not notes and not identity and table_change and not literal_change:
        notes.append('only table numbers would change, and a table has no literal number '
                     'to tell an old tree from an already-renumbered one; move the sections '
                     'that own the tables or rewrite the table references by hand')
    if notes:
        print(f'renumber: root {root}')
        for note in notes:
            print(f'renumber: {note}', file=sys.stderr)
        print('renumber: nothing written', file=sys.stderr)
        return 1

    print(f'renumber: root {root}')
    print(f'renumber: base {args.base}')
    print('structure: identical to --base; old and new numbering coincide'
          if identical_structure else 'structure: changed since --base')
    if applied:
        print('numbering: already at target; nothing to renumber')

    report = Report()
    work_plan = plan.identity() if identity else plan
    rewriter = Rewriter(work_plan, aliases, report, identity=identity)
    print_maps(plan, aliases, identity=identity)

    rewritten: dict[Path, str] = {}
    for document in plan.working:
        text = rewrite_document(document, rewriter)
        if text != document.text:
            rewritten[root / document.path] = text
    rewritten.update(rewrite_yaml(root, rewriter))
    report.dot = report_diagrams(root, work_plan)

    for document in plan.working:
        if not document.generated:
            report.errors.extend(figure_identity_problems(document))

    print(f'CHANGES: {len(report.changes)} references in {len(rewritten)} files')
    for path, line, description in report.changes:
        print(f'  {path}:{line}: {description}')
    print(f'SUSPICIOUS: {len(report.suspicious)} remaining tokens')
    for path, line, token, context in report.suspicious:
        print(f'  {path}:{line}: {token} | {context}')
    print(f'BARE TABLE CELLS: {len(report.bare_cells)}')
    for path, line, text in report.bare_cells:
        print(f'  {path}:{line}: {text}')
    print(f'MANUAL REWRITE: {len(report.manual)}')
    for path, line, description in report.manual:
        print(f'  {path}:{line}: {description}')
    print(f'DIAGRAM LABELS: {len(report.dot)}')
    for path, line, description in report.dot:
        print(f'  {path}:{line}: {description}')
    print('REGENERATE: python3 scripts/generate_catalogs.py; python3 scripts/checklists.py')
    if identity:
        print('renumber: nothing to renumber')

    if report.errors:
        print(f'ERRORS: {len(report.errors)}', file=sys.stderr)
        for error in dict.fromkeys(report.errors):
            print(f'  {error}', file=sys.stderr)
        print('renumber: nothing written', file=sys.stderr)
        return 1

    if args.apply:
        for path, text in rewritten.items():
            path.write_text(text, encoding='utf-8')
        print(f'APPLIED: {len(rewritten)} files written')
    else:
        print('DRY RUN: nothing written (use --apply)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
