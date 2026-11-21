import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_catalogs as gc


class GenerateCatalogsTest(unittest.TestCase):
    def test_committed_appendices_match_the_chapters(self):
        for path, text in gc.targets().items():
            with self.subTest(path=path.name):
                self.assertEqual(path.read_text(encoding='utf-8'), text)

    def test_every_callout_is_listed(self):
        chapters = [gc.chapter_callouts(p) for p in sorted(gc.CHAPTERS.glob('ch*.qmd'))]
        self.assertEqual(len(chapters), 19)
        for number, title, callouts in chapters:
            self.assertIsNotNone(number)
            self.assertTrue(title)
            self.assertTrue(all(section for _, section, _ in callouts))
        for kind, path in (('Common Pitfall', gc.ANTI_PATTERNS), ('Decision & Trade-off', gc.DECISIONS)):
            expected = sum(1 for _, _, c in chapters for x in c if x[0] == kind)
            lines = path.read_text(encoding='utf-8').splitlines()
            rows = [x for x in lines if x.startswith('| ') and not x.startswith(('| Anti-pattern', '| Decision |', '| :---'))]
            self.assertEqual(len(rows), expected)

    def test_pattern_group_caption_keeps_capitals(self):
        catalog = {'AI Systems': [{'name': 'A', 'problem': 'B', 'section': '1.1'}]}
        self.assertIn(': Patterns for AI systems', gc.render_patterns(catalog))

    def test_pattern_entries_match_their_sections(self):
        self.assertEqual(gc.pattern_errors(gc.load_patterns(), gc.section_bodies()), [])

    def test_pattern_error_reports_stale_entry(self):
        catalog = {'Group': [{'name': 'Gone', 'section': '1.1'}, {'name': 'Lost', 'section': '9.9.9'}]}
        errors = gc.pattern_errors(catalog, {'1.1': 'other text'})
        self.assertEqual(len(errors), 2)

    def test_sentence_split_keeps_closing_quote(self):
        self.assertEqual(gc.first_sentence(['A “page.” Then more.']), 'A “page.”')

    def test_decision_extracts_question_and_options(self):
        body = ['Which?', '', '| Option | Choose when | Consequences |', '| :--- | :--- | :--- |', '| A | x | y |', '| B | x | y |']
        self.assertEqual(gc.decision(body), ('Which?', 'A; B'))


if __name__ == '__main__':
    unittest.main()
