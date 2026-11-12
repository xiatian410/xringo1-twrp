#!/usr/bin/env python3
"""Use tiny real EROFS files to check the selective inventory reader."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import inspect_system_partitions as reader


class SystemResources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='erofs-fixture-', dir=ROOT / 'logs')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.original_samples = reader.SAMPLES
        reader.SAMPLES = self.base
        self.addCleanup(setattr, reader, 'SAMPLES', self.original_samples)
        self.source = self.base / 'input'
        for path, text in {
            'system/build.prop': 'ro.build.version.release=17\nro.build.version.security_patch=2026-09-01\n',
            'system/etc/init/a.rc': 'on init\n    setprop test.value 1\n',
            'system/etc/vintf/manifest.xml': '<manifest/>\n',
            'system/app/Test.apk': 'not an APK; deliberately not extracted\n',
        }.items():
            p = self.source / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        (self.source / 'etc').symlink_to('/system/etc')

    def image(self):
        p = self.base / 'sample/system.img'
        p.parent.mkdir(exist_ok=True)
        subprocess.run(['mkfs.erofs', '-T', '0', str(p), str(self.source)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return p, {'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}

    def test_real_image_selected_bytes_and_no_symlink_follow(self):
        _, info = self.image()
        report = reader.inspect('sample', 'system', info)
        self.assertEqual(report['properties']['system/build.prop']['ro.build.version.release'], '17')
        self.assertEqual(report['entries']['etc']['type'], 7)
        self.assertIn('system/app/Test.apk', report['entries'])
        self.assertNotIn('system/app/Test.apk', report['resources'])
        self.assertEqual(len(report['resources']), 3)
        extracted = self.base / 'sample/analysis/system-resources/system'
        self.assertFalse((extracted / 'etc').exists())
        self.assertFalse((extracted / 'system/app/Test.apk').exists())
        for path, item in report['resources'].items():
            self.assertEqual((extracted / path).read_bytes(), (self.source / path).read_bytes())
            self.assertEqual(hashlib.sha256((extracted / path).read_bytes()).hexdigest(), item['sha256'])

    def test_changed_image_rejected_before_extraction(self):
        p, info = self.image()
        p.write_bytes(p.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            reader.inspect('sample', 'system', info)

    def test_conflicting_identity_rejected(self):
        (self.source / 'system/build.prop').write_text('ro.build.version.release=17\nro.build.version.release=16\n')
        _, info = self.image()
        with self.assertRaisesRegex(ValueError, 'conflicting property'):
            reader.inspect('sample', 'system', info)

    def test_host_symlink_image_rejected(self):
        p, info = self.image()
        original = p.with_suffix('.original')
        p.rename(original)
        p.symlink_to(original)
        with self.assertRaisesRegex(ValueError, 'regular'):
            reader.inspect('sample', 'system', info)


if __name__ == '__main__':
    unittest.main(verbosity=2)
