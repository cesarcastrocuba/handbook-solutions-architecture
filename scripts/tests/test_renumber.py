"""Tests for scripts/renumber.py.

Each test builds a synthetic mini-book in a temporary directory: a git
repository with a base commit, then a working tree that holds the NEW structure
and still carries the OLD literal numbers. The script runs exactly as a
contributor runs it, through the command line.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renumber  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / 'renumber.py'
REPO = Path(__file__).resolve().parents[2]


class MiniBook:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def read(self, name: str) -> str:
        return (self.root / name).read_text(encoding='utf-8')

    def replace(self, name: str, old: str, new: str) -> None:
        text = self.read(name)
        if old not in text:
            raise AssertionError(f'{old!r} not in {name}')
        self.write(name, text.replace(old, new, 1))

    def git(self, *args: str) -> None:
        subprocess.run(
            ['git', '-C', str(self.root), '-c', 'user.name=Test',
             '-c', 'user.email=test@example.com', '-c', 'commit.gpgsign=false', *args],
            check=True, capture_output=True, text=True,
        )

    def commit(self, message: str = 'base') -> None:
        self.git('add', '-A')
        self.git('commit', '-m', message)

    def run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--root', str(self.root), '--base', 'HEAD', *args],
            capture_output=True, text=True, cwd=self.root,
        )


def chapter(number: int, title: str, body: str = '') -> str:
    return f'# {number}. {title}\n\n{body}'


class RenumberTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.book = MiniBook(Path(self.tmp.name) / 'book')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def start(self, order: dict[str, list[str]], files: dict[str, str],
              root_files: dict[str, str] | None = None) -> None:
        lines = ['# Reading order for the test book.']
        for group in ('front', 'chapters', 'back', 'appendices', 'references'):
            if group in order:
                lines.append(f'{group}:')
                lines += [f'  - {entry}' for entry in order[group]]
        self.book.write('manuscript/book.yml', '\n'.join(lines) + '\n')
        for name, text in files.items():
            self.book.write(f'manuscript/{name}', text)
        for name, text in (root_files or {}).items():
            self.book.write(name, text)
        self.book.git('init')
        self.book.commit()

    # -- chapter permutation ------------------------------------------------- #

    def test_chapter_permutation(self) -> None:
        files = {
            'chapters/ch01-alpha.qmd': chapter(
                1, 'Alpha', '## 1.1 Requirements\n\nChapter 3 covers gamma.\n'),
            'chapters/ch02-beta.qmd': chapter(
                2, 'Beta', '## 2.1 Principles\n\nDelta is discussed in 1.1.\n'),
            'chapters/ch03-gamma.qmd': chapter(3, 'Gamma', '## 3.1 Detail\n\nBody.\n'),
            'back-matter/conclusions.qmd': (
                '# Conclusions {.unnumbered}\n\n'
                '| Stage | Chapters |\n| :--- | :--- |\n| Read | 1 and 3 |\n'
            ),
        }
        order = {'chapters': ['chapters/ch01-alpha.qmd', 'chapters/ch02-beta.qmd',
                              'chapters/ch03-gamma.qmd'],
                 'back': ['back-matter/conclusions.qmd']}
        self.start(order, files)
        self.book.write('manuscript/book.yml',
                        'chapters:\n'
                        '  - chapters/ch03-gamma.qmd\n'
                        '  - chapters/ch01-alpha.qmd\n'
                        '  - chapters/ch02-beta.qmd\n'
                        'back:\n'
                        '  - back-matter/conclusions.qmd\n')

        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        gamma = self.book.read('manuscript/chapters/ch03-gamma.qmd')
        alpha = self.book.read('manuscript/chapters/ch01-alpha.qmd')
        beta = self.book.read('manuscript/chapters/ch02-beta.qmd')
        self.assertTrue(gamma.startswith('# 1. Gamma'))
        self.assertIn('## 1.1 Detail', gamma)
        self.assertTrue(alpha.startswith('# 2. Alpha'))
        self.assertIn('## 2.1 Requirements', alpha)
        self.assertIn('Chapter 1 covers gamma.', alpha)
        self.assertTrue(beta.startswith('# 3. Beta'))
        self.assertIn('## 3.1 Principles', beta)
        self.assertIn('Delta is discussed in 2.1.', beta)
        conclusions = self.book.read('manuscript/back-matter/conclusions.qmd')
        self.assertIn('| Read | 2 and 1 |', conclusions)

    # -- section moved inside a chapter -------------------------------------- #

    def test_section_moved_with_subsections(self) -> None:
        base = (
            '# 2. Beta\n\n'
            '## 2.1 First\n\n### 2.1.1 One\n\n### 2.1.2 Two\n\n'
            '## 2.2 Second\n\n### 2.2.1 Three\n\n### 2.2.2 Four\n\n'
            'The evidence sits in 2.2.2 and is summarised in 2.1.\n'
        )
        self.start({'chapters': ['chapters/ch01-stable.qmd', 'chapters/ch02-beta.qmd']},
                   {'chapters/ch01-stable.qmd': chapter(1, 'Stable', '## 1.1 Body\n\nText.\n'),
                    'chapters/ch02-beta.qmd': base})
        moved = (
            '# 2. Beta\n\n'
            '## 2.2 Second\n\n### 2.2.1 Three\n\n### 2.2.2 Four\n\n'
            '## 2.1 First\n\n### 2.1.1 One\n\n### 2.1.2 Two\n\n'
            'The evidence sits in 2.2.2 and is summarised in 2.1.\n'
        )
        self.book.write('manuscript/chapters/ch02-beta.qmd', moved)
        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.book.read('manuscript/chapters/ch02-beta.qmd')
        self.assertIn('## 2.1 Second', text)
        self.assertIn('### 2.1.1 Three', text)
        self.assertIn('### 2.1.2 Four', text)
        self.assertIn('## 2.2 First', text)
        self.assertIn('### 2.2.1 One', text)
        self.assertIn('### 2.2.2 Two', text)
        self.assertIn('The evidence sits in 2.1.2 and is summarised in 2.2.', text)

    # -- deleted section, with and without an alias -------------------------- #

    def test_deleted_section_fails_without_alias(self) -> None:
        base = ('# 2. Beta\n\n## 2.1 First\n\n## 2.2 Merged\n\n## 2.3 Third\n\n'
                'See 2.2 and 2.3.\n')
        self.start({'chapters': ['chapters/ch01-stable.qmd', 'chapters/ch02-beta.qmd']},
                   {'chapters/ch01-stable.qmd': chapter(1, 'Stable', '## 1.1 Body\n\nText.\n'),
                    'chapters/ch02-beta.qmd': base})
        self.book.write('manuscript/chapters/ch02-beta.qmd',
                        '# 2. Beta\n\n## 2.1 First\n\n## 2.3 Third\n\nSee 2.2 and 2.3.\n')
        before = self.book.read('manuscript/chapters/ch02-beta.qmd')

        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 1)
        self.assertIn('deleted section 2.2', result.stderr)
        self.assertEqual(self.book.read('manuscript/chapters/ch02-beta.qmd'), before)

        result = self.book.run('--alias', '2.2=2.1', '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.book.read('manuscript/chapters/ch02-beta.qmd')
        self.assertIn('## 2.1 First', text)
        self.assertIn('## 2.2 Third', text)
        self.assertIn('See 2.1 and 2.2.', text)

    # -- deleted figure ------------------------------------------------------- #

    def test_deleted_figure_needs_alias(self) -> None:
        base = (
            '# 1. Alpha\n\n'
            '## 1.1 Evidence\n\n'
            '![Figure 1.1 — One](../../assets/one.png){#fig-1-1 width="100%"}\n\n'
            '![Figure 1.2 — Two](../../assets/two.png){#fig-1-2 width="100%"}\n\n'
            'The figure below is Figure 1.2 and it matters.\n'
        )
        self.start({'chapters': ['chapters/ch01-alpha.qmd']}, {'chapters/ch01-alpha.qmd': base})
        self.book.write(
            'manuscript/chapters/ch01-alpha.qmd',
            '# 1. Alpha\n\n## 1.1 Evidence\n\n'
            '![Figure 1.1 — One](../../assets/one.png){#fig-1-1 width="100%"}\n\n'
            'The figure below is Figure 1.2 and it matters.\n',
        )
        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 1)
        self.assertIn('deleted figure 1.2', result.stderr)

        result = self.book.run('--alias', 'figure:1.2=section:1.1', '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.book.read('manuscript/chapters/ch01-alpha.qmd')
        self.assertIn('The figure below is Section 1.1 and it matters.', text)

    # -- tables follow their caption and their position ----------------------- #

    def test_table_renumbering_after_moved_section(self) -> None:
        def section(number: str, title: str, caption: str) -> str:
            return (f'## {number} {title}\n\n'
                    '| Key | Value |\n| :--- | :--- |\n| a | b |\n\n'
                    f': {caption}\n\n')

        base = ('# 1. Alpha\n\n' + section('1.1', 'First', 'First table caption') +
                section('1.2', 'Second', 'Second table caption') +
                'Compare Table 1.1 with Table 1.2.\n')
        self.start({'chapters': ['chapters/ch01-alpha.qmd']},
                   {'chapters/ch01-alpha.qmd': base})
        moved = ('# 1. Alpha\n\n' + section('1.2', 'Second', 'Second table caption') +
                 section('1.1', 'First', 'First table caption') +
                 'Compare Table 1.1 with Table 1.2.\n')
        self.book.write('manuscript/chapters/ch01-alpha.qmd', moved)

        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.book.read('manuscript/chapters/ch01-alpha.qmd')
        self.assertIn('## 1.1 Second', text)
        self.assertIn('## 1.2 First', text)
        self.assertIn('Compare Table 1.2 with Table 1.1.', text)
        # the second table's caption keeps its wording and moves with the section
        self.assertLess(text.index('Second table caption'), text.index('First table caption'))

    # -- appendix letters swap ------------------------------------------------ #

    def test_appendix_letter_swap(self) -> None:
        files = {
            'chapters/ch01-alpha.qmd': chapter(1, 'Alpha', 'Appendix A lists sources; Appendix B has the rest.\n'),
            'appendices/appendix-a-sources.qmd': (
                '# Appendix A — Sources\n\n![Figure A.1 — Map](../../assets/a.png){#fig-a-1}\n\n'
                '## A.1 Books\n\nText.\n'),
            'appendices/appendix-b-notes.qmd': '# Appendix B — Notes\n\n## B.1 Notes\n\nText B.1.\n',
        }
        order = {'chapters': ['chapters/ch01-alpha.qmd'],
                 'appendices': ['appendices/appendix-a-sources.qmd',
                                'appendices/appendix-b-notes.qmd']}
        self.start(order, files)
        self.book.write('manuscript/book.yml',
                        'chapters:\n  - chapters/ch01-alpha.qmd\n'
                        'appendices:\n  - appendices/appendix-b-notes.qmd\n'
                        '  - appendices/appendix-a-sources.qmd\n')

        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        notes = self.book.read('manuscript/appendices/appendix-b-notes.qmd')
        sources = self.book.read('manuscript/appendices/appendix-a-sources.qmd')
        alpha = self.book.read('manuscript/chapters/ch01-alpha.qmd')
        self.assertTrue(notes.startswith('# Appendix A — Notes'))
        self.assertIn('## A.1 Notes', notes)
        self.assertTrue(sources.startswith('# Appendix B — Sources'))
        self.assertIn('## B.1 Books', sources)
        self.assertIn('![Figure B.1 — Map](../../assets/a.png){#fig-b-1}', sources)
        self.assertIn('Appendix B lists sources; Appendix A has the rest.', alpha)

    # -- appendix section 0 becomes 1 ----------------------------------------- #

    def test_appendix_section_zero_shifts_to_one(self) -> None:
        files = {
            'chapters/ch01-alpha.qmd': chapter(1, 'Alpha', '## 1.1 Body\n\nText.\n'),
            'chapters/ch02-beta.qmd': chapter(2, 'Beta', '## 2.1 Body\n\nText.\n'),
            'appendices/appendix-a-coverage.qmd': (
                '# Appendix A — Coverage\n\n## A.0 Coverage Map\n\nThe map in A.0 and the editions in A.2.\n\n'
                '## A.1 Governance\n\nText.\n\n## A.2 Editions\n\nText.\n'
            ),
        }
        order = {'chapters': ['chapters/ch01-alpha.qmd', 'chapters/ch02-beta.qmd'],
                 'appendices': ['appendices/appendix-a-coverage.qmd']}
        self.start(order, files)
        self.book.write('manuscript/book.yml',
                        'chapters:\n  - chapters/ch02-beta.qmd\n  - chapters/ch01-alpha.qmd\n'
                        'appendices:\n  - appendices/appendix-a-coverage.qmd\n')

        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.book.read('manuscript/appendices/appendix-a-coverage.qmd')
        self.assertIn('## A.1 Coverage Map', text)
        self.assertIn('## A.2 Governance', text)
        self.assertIn('## A.3 Editions', text)
        self.assertIn('The map in A.1 and the editions in A.3.', text)

    # -- version numbers and measurements are not references ------------------ #

    def test_version_numbers_untouched(self) -> None:
        base = (
            '# 1. Alpha\n\n## 1.1 Security\n\n'
            'TLS 1.2 is the floor, OAuth 2.0 and OpenID Connect are covered in Section 1.1, '
            'ISO/IEC 27001:2022 applies and CVSS 3.1 is the score. '
            'Availability is 99.9% with 2.5 ms latency and 2.5 million requests.\n'
        )
        files = {'chapters/ch01-alpha.qmd': base,
                 'chapters/ch02-beta.qmd': chapter(2, 'Beta', '## 2.1 Body\n\nText.\n')}
        order = {'chapters': ['chapters/ch01-alpha.qmd', 'chapters/ch02-beta.qmd']}
        self.start(order, files)
        self.book.write('manuscript/book.yml',
                        'chapters:\n  - chapters/ch02-beta.qmd\n  - chapters/ch01-alpha.qmd\n')

        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.book.read('manuscript/chapters/ch01-alpha.qmd')
        self.assertTrue(text.startswith('# 2. Alpha'))
        self.assertIn('## 2.1 Security', text)
        self.assertIn('covered in Section 2.1', text)
        for untouched in ('TLS 1.2', 'OAuth 2.0', 'ISO/IEC 27001:2022', 'CVSS 3.1',
                          '99.9%', '2.5 ms', '2.5 million'):
            self.assertIn(untouched, text)

    # -- non-contiguous ranges abort the run ---------------------------------- #

    def test_non_contiguous_range_fails(self) -> None:
        names = ('alpha', 'beta', 'gamma', 'delta', 'epsilon')
        files = {
            f'chapters/ch0{index}-{name}.qmd': chapter(
                index, name.title(), 'Chapters 1–3 cover the process.\n' if index == 1 else '')
            for index, name in enumerate(names, 1)
        }
        order = {'chapters': [f'chapters/ch0{i}-{n}.qmd' for i, n in enumerate(names, 1)]}
        self.start(order, files)
        # 3 lands after 5, so chapters 1-3 map to 1, 2 and 4: a hole at 3.
        self.book.write('manuscript/book.yml',
                        'chapters:\n'
                        '  - chapters/ch01-alpha.qmd\n'
                        '  - chapters/ch02-beta.qmd\n'
                        '  - chapters/ch05-epsilon.qmd\n'
                        '  - chapters/ch03-gamma.qmd\n'
                        '  - chapters/ch04-delta.qmd\n')
        before = {name: self.book.read(f'manuscript/{name}') for name in files}

        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 1)
        self.assertIn('not contiguous', result.stderr)
        self.assertIn('MANUAL REWRITE: 1', result.stdout)
        for name, text in before.items():
            self.assertEqual(self.book.read(f'manuscript/{name}'), text)

    # -- ranges --------------------------------------------------------------- #

    def test_range_with_same_set_is_rewritten(self) -> None:
        names = ('alpha', 'beta', 'gamma', 'delta')
        files = {
            f'chapters/ch0{index}-{name}.qmd': chapter(
                index, name.title(),
                'Chapters 2–4 cover the domains; Chapters 1–4 cover the process.\n'
                if index == 1 else '')
            for index, name in enumerate(names, 1)
        }
        order = {'chapters': [f'chapters/ch0{i}-{n}.qmd' for i, n in enumerate(names, 1)]}
        self.start(order, files)
        # 2->1, 3->2, 4->3, 1->4: the range 2-4 still denotes a contiguous set,
        # so it becomes 1-3 instead of failing; 1-4 stays 1-4.
        self.book.write('manuscript/book.yml',
                        'chapters:\n'
                        '  - chapters/ch02-beta.qmd\n'
                        '  - chapters/ch03-gamma.qmd\n'
                        '  - chapters/ch04-delta.qmd\n'
                        '  - chapters/ch01-alpha.qmd\n')
        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.book.read('manuscript/chapters/ch01-alpha.qmd')
        self.assertIn('Chapters 1–3 cover the domains', text)
        self.assertIn('Chapters 1–4 cover the process', text)
        self.assertIn('MANUAL REWRITE: 0', result.stdout)

    def test_non_contiguous_range_is_refused(self) -> None:
        names = ('alpha', 'beta', 'gamma', 'delta', 'epsilon')
        files = {
            f'chapters/ch0{index}-{name}.qmd': chapter(
                index, name.title(), 'Chapters 1–3 cover the process.\n' if index == 1 else '')
            for index, name in enumerate(names, 1)
        }
        order = {'chapters': [f'chapters/ch0{i}-{n}.qmd' for i, n in enumerate(names, 1)]}
        self.start(order, files)
        # order 1,2,5,3,4 maps 1->1, 2->2 and 3->4: the range image has a hole at 3.
        self.book.write('manuscript/book.yml',
                        'chapters:\n'
                        '  - chapters/ch01-alpha.qmd\n'
                        '  - chapters/ch02-beta.qmd\n'
                        '  - chapters/ch05-epsilon.qmd\n'
                        '  - chapters/ch03-gamma.qmd\n'
                        '  - chapters/ch04-delta.qmd\n')
        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 1)
        self.assertIn('not contiguous', result.stderr)
        self.assertIn('MANUAL REWRITE: 1', result.stdout)

    def test_cross_level_range_is_not_fatal(self) -> None:
        files = {
            'chapters/ch01-alpha.qmd': chapter(
                1, 'Alpha', '## 1.1 Body\n\n### 1.1.1 Detail\n\n## 1.4 Tail\n\n'
                            'Covered from 1.1.1–1.4 in one pass.\n'),
            'chapters/ch02-beta.qmd': chapter(2, 'Beta', '## 2.1 Body\n\nText.\n'),
        }
        order = {'chapters': ['chapters/ch01-alpha.qmd', 'chapters/ch02-beta.qmd']}
        self.start(order, files)
        self.book.write('manuscript/book.yml',
                        'chapters:\n  - chapters/ch02-beta.qmd\n  - chapters/ch01-alpha.qmd\n')
        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('crosses section levels', result.stdout)

    # -- appendix letters and generated files --------------------------------- #

    def test_appendix_table_follows_letter_after_rename(self) -> None:
        glossary = (
            '# Appendix A — Glossary\n\nTable A.1 lists the terms.\n\n'
            '| Term | Meaning |\n| :--- | :--- |\n| x | y |\n\n: Glossary of terms\n'
        )
        addendum = (
            '# Appendix B — Addendum\n\n'
            '| Key | Value |\n| :--- | :--- |\n| a | b |\n\n: Addendum table\n'
        )
        files = {
            'chapters/ch01-alpha.qmd': chapter(1, 'Alpha', 'Table A.1 describes the terms.\n'),
            'appendices/appendix-a-glossary.qmd': glossary,
            'appendices/appendix-b-addendum.qmd': addendum,
        }
        order = {'chapters': ['chapters/ch01-alpha.qmd'],
                 'appendices': ['appendices/appendix-a-glossary.qmd',
                                'appendices/appendix-b-addendum.qmd']}
        self.start(order, files)
        # The glossary moves to the last appendix and its file is renamed; the
        # name must not decide that the file is generated, and the table number
        # must follow the letter map, not the path.
        self.book.write('manuscript/appendices/appendix-j-glossary.qmd',
                        glossary.replace('# Appendix A — Glossary', '# Appendix A — Glossary'))
        (self.book.root / 'manuscript' / 'appendices' / 'appendix-a-glossary.qmd').unlink()
        self.book.write('manuscript/book.yml',
                        'chapters:\n  - chapters/ch01-alpha.qmd\n'
                        'appendices:\n  - appendices/appendix-b-addendum.qmd\n'
                        '  - appendices/appendix-j-glossary.qmd\n')
        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        glossary_text = self.book.read('manuscript/appendices/appendix-j-glossary.qmd')
        self.assertTrue(glossary_text.startswith('# Appendix B — Glossary'))
        self.assertIn('Table B.1 lists the terms.', glossary_text)
        alpha = self.book.read('manuscript/chapters/ch01-alpha.qmd')
        self.assertIn('Table B.1 describes the terms.', alpha)
        self.assertTrue(self.book.read('manuscript/appendices/appendix-b-addendum.qmd')
                        .startswith('# Appendix A — Addendum'))

    def test_generated_appendix_is_not_rewritten(self) -> None:
        catalog = (
            '# Appendix A — Pattern Catalog\n\n## A.1 Integration and Messaging\n\n'
            '| Pattern | Section |\n| :--- | :--- |\n| Request/response | 2.1 |\n\n'
            ': Generated pattern index\n'
        )
        files = {
            'chapters/ch01-alpha.qmd': chapter(1, 'Alpha', '## 1.1 Body\n\nText.\n'),
            'appendices/appendix-a-pattern-catalog.qmd': catalog,
            'appendices/appendix-b-notes.qmd': '# Appendix B — Notes\n\n## B.1 Body\n\nText.\n',
        }
        order = {'chapters': ['chapters/ch01-alpha.qmd'],
                 'appendices': ['appendices/appendix-a-pattern-catalog.qmd',
                                'appendices/appendix-b-notes.qmd']}
        self.start(order, files)
        self.book.write('manuscript/book.yml',
                        'chapters:\n  - chapters/ch01-alpha.qmd\n'
                        'appendices:\n  - appendices/appendix-b-notes.qmd\n'
                        '  - appendices/appendix-a-pattern-catalog.qmd\n')
        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('REGENERATE:', result.stdout)
        text = self.book.read('manuscript/appendices/appendix-a-pattern-catalog.qmd')
        self.assertEqual(text, catalog)

    # -- YAML sources --------------------------------------------------------- #

    def test_yaml_sources_follow_the_section_map(self) -> None:
        files = {
            'chapters/ch01-alpha.qmd': chapter(1, 'Alpha', '## 1.1 First\n\n## 1.2 Second\n\nText.\n'),
            'chapters/ch02-beta.qmd': chapter(2, 'Beta', '## 2.1 Body\n\nText.\n'),
        }
        root_files = {
            'publishing/pattern-catalog.yaml': (
                'Group:\n  - {name: Pattern, problem: A problem, section: 2.1}\n'),
            'publishing/index-vocabulary.yaml': (
                "terms:\n- term: Alpha\n  defined: '1.2'\n"
                '  rationale: Ordinary phrase; section 1.2 owns it.\n'),
            'checklists/canonical/app.yaml': (
                'schema_version: 3.0.0\nitems:\n- id: SA-APP-001\n  section: 1.1\n  version: \'2.1\'\n'),
        }
        order = {'chapters': ['chapters/ch01-alpha.qmd', 'chapters/ch02-beta.qmd']}
        self.start(order, files, root_files)
        self.book.write('manuscript/book.yml',
                        'chapters:\n  - chapters/ch02-beta.qmd\n  - chapters/ch01-alpha.qmd\n')

        result = self.book.run('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        pattern = self.book.read('publishing/pattern-catalog.yaml')
        vocabulary = self.book.read('publishing/index-vocabulary.yaml')
        checklist = self.book.read('checklists/canonical/app.yaml')
        self.assertIn('section: 1.1', pattern)
        self.assertIn("defined: '2.2'", vocabulary)
        self.assertIn('section 2.2 owns it.', vocabulary)
        self.assertIn('  section: 2.1', checklist)
        self.assertIn("version: '2.1'", checklist)

    # -- guard rails ---------------------------------------------------------- #

    def test_figure_id_must_match_alt_text(self) -> None:
        files = {
            'chapters/ch01-alpha.qmd': (
                '# 1. Alpha\n\n## 1.1 Body\n\n'
                '![Figure 1.2 — One](../../assets/one.png){#fig-1-1}\n'
            ),
        }
        self.start({'chapters': ['chapters/ch01-alpha.qmd']}, files)
        self.book.write('manuscript/book.yml',
                        'chapters:\n  - chapters/ch01-alpha.qmd\n')
        result = self.book.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn('disagrees with id', result.stderr)

    def test_idempotent_after_apply(self) -> None:
        files = {
            'chapters/ch01-alpha.qmd': chapter(1, 'Alpha', 'Chapters 1 and 2 are distinct.\n'),
            'chapters/ch02-beta.qmd': chapter(2, 'Beta', '## 2.1 Body\n\nSee 2.1.\n'),
        }
        order = {'chapters': ['chapters/ch01-alpha.qmd', 'chapters/ch02-beta.qmd']}
        self.start(order, files)
        self.book.write('manuscript/book.yml',
                        'chapters:\n  - chapters/ch02-beta.qmd\n  - chapters/ch01-alpha.qmd\n')

        first = self.book.run('--apply')
        self.assertEqual(first.returncode, 0, first.stderr)
        after_first = {name: self.book.read(f'manuscript/{name}') for name in files}

        second = self.book.run()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn('CHANGES: 0 references in 0 files', second.stdout)
        for name, text in after_first.items():
            self.assertEqual(self.book.read(f'manuscript/{name}'), text)

        third = self.book.run('--apply')
        self.assertEqual(third.returncode, 0, third.stderr)
        for name, text in after_first.items():
            self.assertEqual(self.book.read(f'manuscript/{name}'), text)

    def test_real_book_at_head_reports_no_changes(self) -> None:
        if not (REPO / '.git').exists() or not (REPO / 'manuscript' / 'book.yml').is_file():
            self.skipTest('not running inside the book repository')
        result = subprocess.run(
            [sys.executable, str(REPO / 'scripts' / 'renumber.py'), '--base', 'HEAD'],
            capture_output=True, text=True, cwd=REPO,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('CHANGES: 0 references in 0 files', result.stdout)


class HelperTest(unittest.TestCase):
    def test_order_key(self) -> None:
        self.assertLess(renumber.order_key('chapter', '9'), renumber.order_key('chapter', '10'))
        self.assertLess(renumber.order_key('section', '4.9'), renumber.order_key('section', '4.10'))
        self.assertLess(renumber.order_key('section', 'B.9'), renumber.order_key('section', 'B.10'))
        self.assertLess(renumber.order_key('appendix', 'G'), renumber.order_key('appendix', 'J'))

    def test_expand_range(self) -> None:
        self.assertEqual(renumber.expand_range('chapter', '5', '7'), ['5', '6', '7'])
        self.assertEqual(renumber.expand_range('section', '4.9', '4.11'),
                         ['4.9', '4.10', '4.11'])
        self.assertEqual(renumber.expand_range('appendix', 'G', 'J'),
                         ['G', 'H', 'I', 'J'])
        self.assertIsNone(renumber.expand_range('section', '4.1.1', '4.4'))
        self.assertIsNone(renumber.expand_range('chapter', '7', '5'))

    def test_split_kind(self) -> None:
        self.assertEqual(renumber.split_kind('figure:8.4'), ('figure', '8.4'))
        self.assertEqual(renumber.split_kind('2.15'), (None, '2.15'))


if __name__ == '__main__':
    unittest.main()
