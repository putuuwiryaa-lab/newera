import hashlib
import json
from pathlib import Path
import unittest

from scripts.export_parity import export

FIXTURES = Path(__file__).parent / 'fixtures'


def digest(snapshot):
    def normalize(value):
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if isinstance(value, float):
            return round(value, 8)
        return value
    return hashlib.sha256(json.dumps(normalize(snapshot), sort_keys=True).encode()).hexdigest()


class ParitySnapshotTests(unittest.TestCase):
    def test_python_production_lifecycle_has_not_changed(self):
        fixture = json.loads((FIXTURES / 'parity_histories.json').read_text())
        expected = json.loads((FIXTURES / 'python-snapshots.json').read_text())
        actual = {f"{case['id']}/{len(step['history'])}": digest(step['python'])
                  for case in export(fixture)['cases'] for step in case['steps']}
        self.assertEqual(actual, expected, 'Production changed: inspect fixture outputs; do not blindly replace the baseline')

    def test_input_retains_twins_leading_zeroes_and_duplicate_events(self):
        fixture = json.loads((FIXTURES / 'parity_histories.json').read_text())
        duplicate = next(c for c in fixture['cases'] if c['id'] == 'consecutive-duplicates-twins')
        self.assertEqual(duplicate['history'][36:39], ['0011', '0011', '9900'])


if __name__ == '__main__':
    unittest.main()
