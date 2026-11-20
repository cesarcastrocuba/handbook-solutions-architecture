"""Canonical review checklists stay in step with the manuscript."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checklists


class ChecklistTests(unittest.TestCase):
    def test_canonical_files_match_manuscript(self):
        self.assertEqual(checklists.check(require_enriched=False), [])

    def test_changed_manuscript_question_is_detected(self):
        original = checklists.manuscript_items
        def altered(rel):
            items = original(rel)
            return [('Changed question?', g) if n == 0 else (q, g) for n, (q, g) in enumerate(items)] if rel == checklists.DOMAINS['SEC'][1] else items
        with mock.patch.object(checklists, 'manuscript_items', altered):
            self.assertTrue(any('SA-SEC' in e for e in checklists.check(require_enriched=False)))

    def test_retired_identifier_cannot_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            retired = Path(tmp)/'retired-ids.txt'
            retired.write_text('SA-SEC-001\n')
            with mock.patch.object(checklists, 'RETIRED', retired):
                self.assertTrue(any('retired' in e for e in checklists.check(require_enriched=False)))

    def test_assessment_template_has_blank_outcomes(self):
        records = [{k: r[k] for k in ('id', 'domain', 'question')} for r in checklists.rows()]
        template = checklists.csv_text(records, checklists.ASSESSMENT).splitlines()
        self.assertEqual(template[0].split(','), checklists.ASSESSMENT)
        self.assertTrue(all(line.endswith(',,,,,,,,') for line in template[1:]))

class ImportedChecklistTests(unittest.TestCase):
    def test_title_attribute_keeps_questions_and_stops_at_callout_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = root/'manuscript/chapters/example.qmd'
            chapter.parent.mkdir(parents=True)
            chapter.write_text('''# Example
::: {.callout-note .review title="Architecture Review Checklist — Example"}
☐ First question?
☐ Second question?
:::
☐ Outside the checklist?
''')
            with mock.patch.object(checklists, 'ROOT', root):
                self.assertEqual(checklists.manuscript_items('chapters/example.qmd'),
                                 [('First question?', None), ('Second question?', None)])

    def test_wrong_title_does_not_silently_accept_a_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = root/'manuscript/chapters/example.qmd'
            chapter.parent.mkdir(parents=True)
            chapter.write_text('::: {.callout-note title="Other"}\n☐ Question?\n:::\n')
            with mock.patch.object(checklists, 'ROOT', root):
                with self.assertRaises(StopIteration):
                    checklists.manuscript_items('chapters/example.qmd')

    def test_exports_preserve_records_and_do_not_modify_canonical_data(self):
        import json
        before = {p: p.read_bytes() for p in checklists.CANONICAL.glob('*.yaml')}
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(checklists, 'EXPORTS', Path(tmp)):
                changed, count = checklists.export()
                self.assertEqual(changed, 4)
                self.assertEqual(count, 157)
                self.assertEqual(json.loads((Path(tmp)/'architecture-review-checklist.json').read_text()),
                                 list(checklists.rows()))
                self.assertEqual(checklists.export(), (0, count))
        self.assertEqual(before, {p: p.read_bytes() for p in before})


if __name__ == '__main__':
    unittest.main()
