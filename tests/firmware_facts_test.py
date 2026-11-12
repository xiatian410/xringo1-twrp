#!/usr/bin/env python3
"""Cross-check module parsing with libkmod and reject malformed archive layouts."""
from pathlib import Path
import struct
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from firmware_facts import boot_parts, elf_module, ramdisk_entries, haptics_module
from acquire_firmware import sources
from repack_ramdisk import emit_cpio


class FirmwareFactsTest(unittest.TestCase):
    def test_imports_and_exports_match_independent_libkmod(self):
        paths = []
        for sample in sources():
            base = ROOT / 'firmware/samples' / sample / 'analysis/vendor_dlkm'
            for mod in ['xring_smartpa.ko', 'xring_audio_hw_third.ko', 'synaptics_tcm2.ko']:
                paths.extend(base.rglob(mod))
        self.assertEqual(len(paths), 2 * len(sources()))
        for path in paths:
            result = elf_module(path.read_bytes())
            for option, key in [('--show-modversions', 'imports'), ('--show-exports', 'exports')]:
                # These modprobe options only inspect a regular ELF file; no load.
                proc = subprocess.run(['modprobe', option, str(path)], text=True, capture_output=True)
                if key == 'exports' and proc.returncode == 1 and 'No data available' in proc.stderr:
                    self.assertEqual(result[key], {}, path)
                    continue
                self.assertEqual(proc.returncode, 0, proc.stderr)
                out = proc.stdout
                reference = {line.split()[1]: int(line.split()[0], 16) for line in out.splitlines() if line.strip()}
                self.assertEqual(result[key], reference, (path, key))

    def test_haptics_selection_uses_probe_and_rejects_ambiguity(self):
        import json
        for sample in sources():
            facts = json.loads((ROOT / f'firmware/samples/{sample}/analysis/facts.json').read_text())
            path, module = haptics_module(facts)
            self.assertTrue(path.startswith('vendor_dlkm/'))
            self.assertIn('cs40l26_i2c_probe', module['exports'])
            facts['sample'] = 'arbitrary-future-profile-name'
            self.assertEqual(haptics_module(facts)[0], path)
            facts['modules']['vendor_dlkm/duplicate.ko'] = module
            with self.assertRaisesRegex(ValueError, 'expected one stock'):
                haptics_module(facts)
        with self.assertRaisesRegex(ValueError, 'expected one stock'):
            haptics_module({'sample': 'missing', 'modules': {}})

    def test_same_layout_does_not_mean_touch_abi_matches(self):
        a, b = [elf_module((ROOT / f'firmware/samples/{s}/analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko').read_bytes())
                for s in ['os3-initial', 'os3-final']]
        self.assertEqual(a['module_layout_crc'], b['module_layout_crc'])
        self.assertNotEqual(a['imports']['register_touch_panel'], b['imports']['register_touch_panel'])
        self.assertNotEqual(a['imports']['add_common_data_to_buf'], b['imports']['add_common_data_to_buf'])

    def test_crc_name_in_unrelated_bytes_is_ignored(self):
        path = ROOT / 'imgs/firmware/vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        original = path.read_bytes()
        data = bytearray(original)
        # An ELF header's unused identification padding is not a version record.
        # Place the decoy in the first allocatable section instead, leaving the
        # version table and symbol/section offsets intact. Target code is never run.
        shoff, = struct.unpack_from('<Q', data, 40)
        firstoff, firstsize = struct.unpack_from('<QQ', data, shoff + 64 + 24)
        self.assertGreater(firstsize, 32)
        decoy = struct.pack('<Q', 0x12345678) + b'module_layout\0'
        data[firstoff:firstoff + len(decoy)] = decoy
        self.assertEqual(elf_module(data)['imports'], elf_module(original)['imports'])

    def test_cpio_paths_and_lengths_are_checked(self):
        def archive(name):
            return emit_cpio([(name, 0o100644, 0, 0, 1, 0, 1, 0, 0, 0, 0, b'x')])
        self.assertEqual(ramdisk_entries(archive('etc/test'))[0][0], 'etc/test')
        for name in ['../outside', '/absolute', 'a/../../outside']:
            with self.assertRaises(ValueError):
                ramdisk_entries(archive(name))
        with self.assertRaises(ValueError):
            ramdisk_entries(archive('test')[:113])

    def test_boot_v4_signature_size_and_bounds(self):
        image = bytearray(4096 * 3)
        image[:8] = b'ANDROID!'
        struct.pack_into('<4I', image, 8, 0, 1, 0, 1584)
        struct.pack_into('<I', image, 40, 4)
        struct.pack_into('<I', image, 1580, 3)
        image[4096] = 1
        image[8192:8195] = b'sig'
        _, parts = boot_parts(image)
        self.assertEqual(parts['boot_signature'], b'sig')
        with self.assertRaises(ValueError):
            boot_parts(image[:8194])


if __name__ == '__main__':
    unittest.main()
