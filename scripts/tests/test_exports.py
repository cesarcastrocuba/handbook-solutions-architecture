"""Generated checklist deliverables validate frozen data and stay outside source."""
import csv
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
import export_checklists_csv as exports


class ExportTests(unittest.TestCase):
    def test_reference_self_test(self):
        self.assertEqual(exports.run_self_test(ROOT/'checklists/schema/checklist.schema.json'), 0)

    def test_all_frozen_data_exports_validate_and_preserve_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            result = subprocess.run([sys.executable, str(ROOT/'scripts/export_checklists_csv.py'),
                                     '--all', '--output-dir', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            inputs = sorted((ROOT/'checklists/data').glob('*-source-checklist.yaml'))
            self.assertEqual(len(inputs), 15)
            self.assertEqual(len(list(output.glob('*.csv'))), len(inputs) + 2)
            for path in inputs:
                data = exports.parse_simple_checklist_yaml(path.read_text())
                with (output/(path.stem+'.csv')).open() as stream:
                    self.assertEqual(list(csv.DictReader(stream)), data['items'])
            pilot = exports.parse_simple_checklist_yaml((ROOT/'checklists/data/ch06-integration-checklist.yaml').read_text())
            self.assertEqual((output/'ch06-integration-checklist.csv').read_text(), exports.render_csv(pilot))
            with (output/'all-checklists.csv').open() as stream:
                aggregate = list(csv.DictReader(stream))
            self.assertEqual(len(aggregate), 96)
            integration = [row for row in aggregate if row['id'].startswith('CHK-CH06-')]
            self.assertEqual([row['question'] for row in integration], [item['question'] for item in pilot['items']])
            self.assertEqual([row['source_id'] for row in integration],
                             [f'RC2-B{number:04d}' for number in range(791, 796)])

    def test_invalid_schema_and_pilot_range_fail(self):
        for mutation in ('schema', 'range'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shutil.copytree(ROOT/'checklists', root/'checklists')
                if mutation == 'schema':
                    path = root/'checklists/data/ch01-source-checklist.yaml'
                    data = json.loads(path.read_text());data['items'][0]['question'] = 42
                    path.write_text(json.dumps(data))
                else:
                    path = root/'checklists/data/ch06-integration-checklist.yaml'
                    path.write_text(path.read_text().replace('DOCX[790..795]', 'DOCX[790..799]'))
                result = subprocess.run([sys.executable, str(ROOT/'scripts/export_checklists_csv.py'),
                                         '--all', '--repo-root', str(root)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('CHECKLIST_ERROR:', result.stderr)
                self.assertFalse((root/'checklists/exports').exists())
