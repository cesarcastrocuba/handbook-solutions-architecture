#!/usr/bin/env python3
"""Generate Appendices H (anti-patterns), I (decisions) and J (patterns).

Every "Common Pitfall" and "Decision & Trade-off" callout is listed with the
section that discusses it. Appendix G comes from publishing/pattern-catalog.yaml,
and each entry must still be discussed in the section it names. The appendices
are derived data: edit the sources and run this script. With --check, exit 1 if
a committed appendix is out of date.
"""
import argparse
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = ROOT/'manuscript'/'chapters'
APPENDICES = ROOT/'manuscript'/'appendices'
ANTI_PATTERNS = APPENDICES/'appendix-h-anti-pattern-catalog.qmd'
DECISIONS = APPENDICES/'appendix-i-decision-catalog.qmd'
PATTERNS = APPENDICES/'appendix-g-pattern-catalog.qmd'
PATTERN_SOURCE = ROOT/'publishing'/'pattern-catalog.yaml'
H1 = re.compile(r'^# (?:Chapter )?(\d+)[.:—\s]+(.+)$')
H2 = re.compile(r'^## (\d+\.\d+) ')
CALLOUT = re.compile(r'^::: \{\.callout-\w+ [^}]*title="(Common Pitfall|Decision & Trade-off)"')
SENTENCE_END = re.compile(r'(?:(?<=[.!?])|(?<=[.!?][”"’]))\s+(?=[A-Z“"‘])')


def chapter_callouts(path):
    """Return (chapter number, title, [(kind, section, body lines)]) for one chapter."""
    number, title, section, found, current = None, None, None, [], None
    for line in path.read_text(encoding='utf-8').splitlines():
        if current is not None:
            if line.strip() == ':::':
                found.append(current)
                current = None
            else:
                current[2].append(line)
        elif number is None and (match := H1.match(line)):
            number, title = int(match[1]), match[2].strip()
        elif match := H2.match(line):
            section = match[1]
        elif match := CALLOUT.match(line):
            current = (match[1], section, [])
    return number, title, found


def cell(text):
    return text.strip().replace('|', r'\|')


def first_sentence(lines):
    return SENTENCE_END.split(' '.join(x.strip() for x in lines if x.strip()), maxsplit=1)[0]


def decision(lines):
    """Return the question and the option names of a decision callout."""
    prose = [x.strip() for x in lines if x.strip() and not x.startswith('|')]
    rows = [x for x in lines if x.startswith('|')][2:]
    options = [x.strip('|').split('|')[0].strip() for x in rows]
    return ' '.join(prose), '; '.join(options)


def render(chapters, kind):
    pitfalls = kind == 'Common Pitfall'
    letter = 'H' if pitfalls else 'I'
    out = ['# Appendix H — Anti-Pattern Catalog' if pitfalls else '# Appendix I — Decision Catalog', '']
    if pitfalls:
        out += ['This catalog lists the anti-patterns described in the Common Pitfall callouts of each '
                'chapter, so that a review can scan them in one place. Each entry names the problem; '
                'the section it links to explains the consequences and what to do instead.', '']
    else:
        out += ['This catalog lists the recurring decisions from the Decision & Trade-off callouts of '
                'each chapter, with the options compared. The section each entry links to gives the '
                'conditions for choosing an option and the consequences.', '']
    for index, (number, title, callouts) in enumerate(chapters, 1):
        out += [f'## {letter}.{index} Chapter {number}: {title}', '']
        if pitfalls:
            out += ['| Anti-pattern | Section |', '| :--- | :--- |']
            out += [f'| {cell(first_sentence(body))} | {section} |'
                    for found, section, body in callouts if found == kind]
            out += ['', f': Anti-patterns from Chapter {number}', '']
        else:
            out += ['| Decision | Options compared | Section |', '| :--- | :--- | :--- |']
            for found, section, body in callouts:
                if found == kind:
                    question, options = decision(body)
                    out.append(f'| {cell(question)} | {cell(options)} | {section} |')
            out += ['', f': Decisions from Chapter {number}', '']
    return '\n'.join(out).rstrip('\n')+'\n'


def section_bodies():
    """Map every numbered section to its text, including its subsections."""
    bodies = {}
    heading = re.compile(r'^(#{2,4}) (\d+\.\d+(?:\.\d+)?) ')
    for path in sorted(CHAPTERS.glob('ch*.qmd')):
        lines = path.read_text(encoding='utf-8').splitlines()
        marks = [(i, len(m[1]), m[2]) for i, line in enumerate(lines) if (m := heading.match(line))]
        for position, (start, level, number) in enumerate(marks):
            end = next((i for i, other, _ in marks[position+1:] if other <= level), len(lines))
            bodies[number] = '\n'.join(lines[start:end])
    return bodies


def load_patterns(source=PATTERN_SOURCE):
    return yaml.safe_load(source.read_text(encoding='utf-8'))


def pattern_errors(catalog, bodies):
    """Entries whose section is missing or no longer discusses the pattern."""
    errors = []
    for entries in catalog.values():
        for entry in entries:
            section, term = str(entry['section']), entry.get('match', entry['name'])
            if section not in bodies:
                errors.append(f'{entry["name"]}: section {section} does not exist')
            elif term.casefold() not in bodies[section].casefold():
                errors.append(f'{entry["name"]}: "{term}" not found in section {section}')
    return errors


def render_patterns(catalog):
    out = ['# Appendix G — Pattern Catalog', '',
           'This catalog locates the patterns discussed in the handbook. It is an index and not a '
           'recommendation: the section named for each pattern explains when it applies and what it costs.', '']
    for index, (category, entries) in enumerate(catalog.items(), 1):
        out += [f'## G.{index} {category}', '', '| Pattern | Problem it addresses | Section |', '| :--- | :--- | :--- |']
        out += [f'| {cell(e["name"])} | {cell(e["problem"])} | {e["section"]} |' for e in entries]
        group = ' '.join(w if w.isupper() else w.lower() for w in category.split())
        out += ['', f': Patterns for {group}', '']
    return '\n'.join(out).rstrip('\n')+'\n'


def targets():
    chapters = [chapter_callouts(path) for path in sorted(CHAPTERS.glob('ch*.qmd'))]
    return {ANTI_PATTERNS: render(chapters, 'Common Pitfall'), DECISIONS: render(chapters, 'Decision & Trade-off'),
            PATTERNS: render_patterns(load_patterns())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail if a committed appendix is out of date')
    args = parser.parse_args()
    errors = pattern_errors(load_patterns(), section_bodies())
    if errors:
        print('\n'.join(errors))
        return 1
    stale = []
    for path, text in targets().items():
        if not path.exists() or path.read_text(encoding='utf-8') != text:
            stale.append(path.relative_to(ROOT))
            if not args.check:
                path.write_text(text, encoding='utf-8')
    if args.check and stale:
        for path in stale:
            print(f'{path}: out of date; run scripts/generate_catalogs.py')
        return 1
    print(f'CATALOGS: {len(targets())} appendices {"checked" if args.check else "generated"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
