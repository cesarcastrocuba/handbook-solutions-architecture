"""House style: text separates every table from the next table or figure, and every figure from the next float."""
import re
import unittest
from pathlib import Path

MANUSCRIPT = Path(__file__).resolve().parents[2] / 'manuscript'
CAPTION = re.compile(r':\s+\S')


def floats(text):
    """Yield (kind, line) for each table, figure and prose block, in order."""
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('|'):
            start = i
            while i < len(lines) and lines[i].startswith('|'):
                i += 1
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and CAPTION.match(lines[j]):
                i = j + 1
            yield 'float', start + 1
            continue
        if line.startswith('!['):
            yield 'float', i + 1
        elif line.strip() and not line.startswith((':::', '<!--')):
            yield 'text', i + 1
        i += 1


def adjacent(path):
    blocks = list(floats(path.read_text(encoding='utf-8')))
    return [first[1] for first, second in zip(blocks, blocks[1:]) if first[0] == second[0] == 'float']


class FloatSpacingTest(unittest.TestCase):
    def test_no_float_follows_another_without_text(self):
        for path in sorted(MANUSCRIPT.glob('*/*.qmd')):
            with self.subTest(path=path.name):
                self.assertEqual(adjacent(path), [], 'add a sentence between these floats')

    def test_detector_finds_a_table_followed_by_a_figure(self):
        text = '| a |\n| :--- |\n| b |\n\n: Caption\n\n![Figure 1.1 — x](x.png){#fig-1-1}\n'
        self.assertEqual([k for k, _ in floats(text)], ['float', 'float'])
        text = '| a |\n| :--- |\n| b |\n\n: Caption\n\nA bridge.\n\n![Figure 1.1 — x](x.png){#fig-1-1}\n'
        self.assertEqual([k for k, _ in floats(text)], ['float', 'text', 'float'])


if __name__ == '__main__':
    unittest.main()
