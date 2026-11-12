#!/usr/bin/env python3
"""Ensure the inventory rejects stale/missing bindings and never upgrades text logs."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_evidence_freshness import digest, inventory


class Freshness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evidence-freshness-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'image').write_bytes(b'private test artifact')
        (self.root / 'source').write_text('current source')
        self.write_report(dict(status='PASS', sources={'source': digest(self.root / 'source')},
                               image_sha256=digest(self.root / 'image')))

    def write_report(self, report):
        (self.root / 'report.json').write_text(json.dumps(report))
        self.index = dict(image='image', image_sha256=digest(self.root / 'image'),
                          checks=[dict(name='fixture', evidence='report.json',
                                       evidence_sha256=digest(self.root / 'report.json'))], additional_checks=[])

    def run_inventory(self):
        return inventory(self.index, self.root, self.root / 'android')

    def test_current(self):
        report = self.run_inventory()
        self.assertEqual(report['status'], 'CURRENT_BINDINGS')
        self.assertEqual(report['counts'], dict(matched=1, drift=0, unbound=0))
        self.assertEqual(report['functional_completion'], 'not assessed')

    def test_changed_source(self):
        (self.root / 'source').write_text('source edited after test')
        row, = self.run_inventory()['entries']
        self.assertEqual(row['binding'], 'drift')
        self.assertEqual(row['mismatches'][0]['kind'], 'dependency')

    def test_changed_evidence(self):
        (self.root / 'report.json').write_text('{}')
        row, = self.run_inventory()['entries']
        self.assertEqual(row['mismatches'][0]['kind'], 'indexed-evidence')

    def test_replaced_image(self):
        (self.root / 'image').write_bytes(b'different artifact')
        report = self.run_inventory()
        self.assertFalse(report['image_matches'])
        self.assertEqual(report['entries'][0]['mismatches'][0]['kind'], 'artifact')

    def test_missing_inputs(self):
        (self.root / 'source').unlink()
        (self.root / 'image').unlink()
        report = self.run_inventory()
        self.assertEqual(report['status'], 'NOT_CURRENT')
        self.assertFalse(report['image_matches'])
        self.assertEqual(len(report['entries'][0]['mismatches']), 2)

    def test_text_log_unbound(self):
        (self.root / 'report.json').write_text('PASS\n')
        self.index['checks'][0]['evidence_sha256'] = digest(self.root / 'report.json')
        self.assertEqual(self.run_inventory()['counts'], dict(matched=0, drift=0, unbound=1))

    def test_nested_map(self):
        self.write_report(dict(lvgl=dict(source_files={'source': digest(self.root / 'source')})))
        self.assertEqual(self.run_inventory()['counts']['matched'], 1)
        (self.root / 'source').write_text('changed')
        row, = self.run_inventory()['entries']
        self.assertEqual(row['mismatches'][0]['field'], 'lvgl.source_files')

    def test_malformed_map_not_silently_skipped(self):
        self.write_report(dict(sources={'source': digest(self.root / 'source')}, tests={'bad': 1}))
        self.assertEqual(self.run_inventory()['counts']['unbound'], 1)

    def test_settings_explicit_path_schema(self):
        source = self.root / 'android/bootable/recovery'
        source.mkdir(parents=True)
        sources = {}
        for name in ['data.cpp', 'infomanager.cpp', 'infomanager.hpp', 'variables.h']:
            (source / name).write_text(name)
            sources[name] = digest(source / name)
        self.write_report(dict(sources=sources))
        self.assertEqual(self.run_inventory()['counts']['matched'], 1)

    def test_failed_test_is_not_a_functional_pass(self):
        self.write_report(dict(status='FAIL', sources={'source': digest(self.root / 'source')}))
        report = self.run_inventory()
        self.assertEqual(report['entries'][0]['recorded_status'], 'FAIL')
        self.assertEqual(report['functional_completion'], 'not assessed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
