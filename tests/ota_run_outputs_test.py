#!/usr/bin/env python3
"""Check evidence preservation without executing the OTA engine or a device."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from ota_run_outputs import output_prefix, reserve_outputs

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = ['.json', '.stdout', '.stderr', '.adapter.cpp', '.support.inc']


class OutputPreservation(unittest.TestCase):
    def test_existing_outputs_are_preserved(self):
        for suffix in SUFFIXES:
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / ('run' + suffix)
                path.write_bytes(b'original evidence\n')
                with self.assertRaisesRegex(FileExistsError, 'Preserve existing evidence'):
                    reserve_outputs(tmp, 'run', SUFFIXES)
                self.assertEqual(path.read_bytes(), b'original evidence\n')
                self.assertFalse((Path(tmp) / 'run.reservation').exists())

    def test_dangling_symlink_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'run.json'
            path.symlink_to('missing')
            with self.assertRaises(FileExistsError):
                reserve_outputs(tmp, 'run', SUFFIXES)
            self.assertTrue(path.is_symlink())

    def test_reservation_survives_absent_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            reserve_outputs(tmp, 'run', SUFFIXES)
            with self.assertRaisesRegex(FileExistsError, 'Run already reserved'):
                reserve_outputs(tmp, 'run', SUFFIXES)

    def test_concurrent_reservation_has_one_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            barrier = threading.Barrier(2)

            def attempt(_):
                barrier.wait()
                try:
                    reserve_outputs(tmp, 'run', SUFFIXES)
                    return 'owner'
                except FileExistsError:
                    return 'refused'

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertCountEqual(list(pool.map(attempt, range(2))), ['owner', 'refused'])

    def test_run_names_are_independent_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ['first', 'second_2', 'third-3']:
                reserve_outputs(tmp, output_prefix('run', name), SUFFIXES)
            self.assertEqual(output_prefix('run'), 'run')
            for name in ['', '../escape', '/absolute', 'a/b', 'a.b', 'a b', '中文', 'a' * 81]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    output_prefix('run', name)

    def test_existing_cli_defaults_stop_before_execution(self):
        # Use existing evidence only to check fail-fast behaviour. Never select
        # a fresh run name here: that would start an expensive OTA execution.
        commands = [
            ('ota_engine_entry.py', ['--join-zip', '--model-finish', '--allocate-snapshots'],
             'zip-engine-allocated-finish', ['.json', '.stdout', '.stderr']),
            ('ota_allocated_exit_probe.py', [], 'ota-allocated-exit-probe', ['.json']),
        ]
        for script, args, prefix, suffixes in commands:
            with self.subTest(script=script):
                paths = [ROOT / 'logs' / (prefix + suffix) for suffix in suffixes]
                self.assertTrue(all(path.is_file() for path in paths), 'Existing evidence required')
                before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
                result = subprocess.run([sys.executable, str(ROOT / 'tests' / script), *args],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('Preserve existing evidence:', result.stderr)
                self.assertEqual(before, [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths])


if __name__ == '__main__':
    unittest.main(verbosity=2)
