#!/usr/bin/env python3
"""Execute the real read-only selector against copied, verified OTA evidence.

Only /proc and dm mount evidence are synthetic. Identity/module/blob bytes come
from the named original packages. No mounts, HAL calls or device writes occur.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from acquire_firmware import sources

ROOT = Path(__file__).resolve().parents[1]
TREE = ROOT / 'dtsrc/O1_asic_dual'
SCRIPT = TREE / 'profiles/runtime/dijun-select-profile.sh'
CATALOG = TREE / 'profiles'
BLOBS = TREE / 'prebuilt/common/profile-blobs'
SAMPLES = sorted(p.parent.name for p in CATALOG.glob('*/selection.conf'))
RESULTS = []


class Selection(unittest.TestCase):
    def fixture(self, sample, slot='_a'):
        temp = tempfile.TemporaryDirectory(prefix='dijun-profile-test-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        sources = json.loads((CATALOG / sample / 'selection-sources.json').read_text())
        for dest, item in sources.items():
            target = root / dest.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            assert hashlib.sha256((ROOT / item['source']).read_bytes()).hexdigest() == item['sha256']
            shutil.copy2(ROOT / item['source'], target)
        kernel = json.loads((CATALOG / sample / 'profile.json').read_text())['kernel_release']
        p = root / 'proc/sys/kernel/osrelease'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(kernel + '\n')
        (root / 'proc/bootconfig').write_text(f'androidboot.slot_suffix = "{slot}"\n')
        mounts = []
        for i, partition in enumerate(['system', 'vendor', 'odm', 'vendor_dlkm']):
            point = '/system_root' if partition == 'system' else '/' + partition
            mounts.append(f'/dev/block/dm-{i} {point} erofs ro 0 0')
            p = root / f'sys/class/block/dm-{i}/dm/name'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(partition + slot + '\n')
        (root / 'proc/mounts').write_text('\n'.join(mounts) + '\n')
        return root

    def run_selector(self, root, expected, case, catalog=CATALOG, blobs=BLOBS):
        result = subprocess.run(['sh', str(SCRIPT), '--root', str(root),
                                 '--profiles', str(catalog), '--blobs', str(blobs)],
                                capture_output=True, text=True, timeout=10)
        RESULTS.append(dict(case=case, expected_exit=expected, actual_exit=result.returncode,
                            stdout=result.stdout, stderr=result.stderr))
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_all_slots_and_readonly(self):
        for sample in SAMPLES:
            for slot in ['_a', '_b']:
                with self.subTest(sample=sample, slot=slot):
                    root = self.fixture(sample, slot)
                    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in root.rglob('*') if p.is_file()}
                    result = self.run_selector(root, 0, f'{sample}:{slot}:matching')
                    self.assertIn(f'PROFILE={sample}\n', result.stdout)
                    self.assertIn(f'SLOT={slot}\n', result.stdout)
                    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in root.rglob('*') if p.is_file()}
                    self.assertEqual(before, after, 'selector must not mutate evidence')

    def test_wrong_kernel_and_component_bytes(self):
        for sample in SAMPLES:
            for path in ['proc/sys/kernel/osrelease', 'system_root/system/build.prop',
                         'vendor/build.prop', 'odm/etc/build.prop', 'vendor/etc/fstab.O1_asic',
                         'vendor_dlkm/lib/modules/synaptics_tcm2.ko']:
                with self.subTest(sample=sample, path=path):
                    root = self.fixture(sample)
                    p = root / path
                    p.write_bytes(p.read_bytes().rstrip(b'\n') + b'-changed\n')
                    self.run_selector(root, 3, f'{sample}:modified:{path}')

    def test_missing_source_and_unknown_release(self):
        for sample in SAMPLES:
            root = self.fixture(sample)
            (root / 'vendor/etc/fstab.O1_asic').unlink()
            self.run_selector(root, 3, f'{sample}:missing-fstab')
        root = self.fixture(SAMPLES[0])
        (root / 'proc/sys/kernel/osrelease').write_text('6.6.77-unreviewed-kernel\n')
        self.run_selector(root, 3, 'same-major-minor-is-insufficient')

    def test_conflicting_slot_mounts(self):
        sample = SAMPLES[0]
        for partition in range(4):
            root = self.fixture(sample)
            p = root / f'sys/class/block/dm-{partition}/dm/name'
            p.write_text(p.read_text().replace('_a', '_b'))
            self.run_selector(root, 2, f'inactive-slot-mount:{partition}')
        for text in ['', 'androidboot.slot_suffix = "_c"\n',
                     'androidboot.slot_suffix = "_a"\nandroidboot.slot_suffix = "_b"\n']:
            root = self.fixture(sample)
            (root / 'proc/bootconfig').write_text(text)
            self.run_selector(root, 2, f'invalid-slot:{text.strip()}')
        root = self.fixture(sample)
        p = root / 'proc/mounts'
        p.write_text(p.read_text() + p.read_text().splitlines()[0] + '\n')
        self.run_selector(root, 2, 'duplicate-system-mount')

    def test_missing_and_corrupt_blobs(self):
        sample = SAMPLES[0]
        root = self.fixture(sample)
        blobs = root / 'blobs'
        blobs.mkdir()
        self.run_selector(root, 3, 'empty-blob-store', blobs=blobs)
        # Independent copies; corruption must never change the original blobs.
        assets = json.loads((CATALOG / sample / 'profile.json').read_text())['assets']
        for sha in {a['sha256'] for a in assets.values()}:
            shutil.copy2(BLOBS / sha, blobs / sha)
        sha = sorted(a['sha256'] for a in assets.values())[0]
        p = blobs / sha
        p.write_bytes(b'corrupt' + p.read_bytes()[7:])
        self.run_selector(root, 3, 'corrupted-blob-store', blobs=blobs)

    def test_ambiguity_and_malformed_manifest(self):
        sample = SAMPLES[0]
        root = self.fixture(sample)
        catalog = root / 'catalog'
        for name in [sample, sample + '-copy']:
            (catalog / name).mkdir(parents=True)
            shutil.copy2(CATALOG / sample / 'selection.conf', catalog / name / 'selection.conf')
        self.run_selector(root, 4, 'ambiguous-identical-profiles', catalog=catalog)
        shutil.rmtree(catalog / (sample + '-copy'))
        p = catalog / sample / 'selection.conf'
        original = p.read_text()
        p.write_text(original.replace('schema 1', 'schema 2'))
        self.run_selector(root, 2, 'unsupported-schema', catalog=catalog)
        p.write_text('\n'.join(line for line in original.splitlines() if not line.startswith('identity haptics ')) + '\n')
        self.run_selector(root, 2, 'missing-mandatory-haptics-anchor', catalog=catalog)

    def test_actual_cross_version_touch_swap(self):
        if not {'os3-initial', 'os3-final'} <= set(SAMPLES):
            self.skipTest('both OS3 system identities not yet acquired')
        root = self.fixture('os3-initial')
        source = ROOT / 'firmware/samples/os3-final/analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        shutil.copy2(source, root / 'vendor_dlkm/lib/modules/synaptics_tcm2.ko')
        self.run_selector(root, 3, 'OS3-final-touch-on-OS3-initial')

    def test_os4_stable_mixed_components_rejected(self):
        if not {'os4-current', 'os4-stable'} <= set(SAMPLES):
            self.skipTest('stable OS4 not staged')
        for source, target in [('os4-current', 'os4-stable'), ('os4-stable', 'os4-current')]:
            other = json.loads((CATALOG/source/'selection-sources.json').read_text())
            own = json.loads((CATALOG/target/'selection-sources.json').read_text())
            for runtime in other.keys() & own.keys():
                if other[runtime]['sha256'] == own[runtime]['sha256']:
                    continue
                root = self.fixture(target)
                shutil.copy2(ROOT/other[runtime]['source'], root/runtime.lstrip('/'))
                self.run_selector(root, 3, f'{source}-component-on-{target}:{runtime}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    if not SAMPLES or (set(SAMPLES) != set(sources()) and not args.allow_partial):
        raise SystemExit('Generate selection manifests for the complete source catalog first (or explicitly --allow-partial).')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Selection)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = dict(status='PASS' if result.wasSuccessful() else 'FAIL', samples=SAMPLES,
                  scope='Actual read-only selector; fixture mounts, original package bytes. Selection only; activation is covered by a separate actual-image test.',
                  selector_sha256=hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
                  test_sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),ROOT/'scripts/acquire_firmware.py']},
                  tests_run=result.testsRun, skipped=len(result.skipped), cases=RESULTS)
    (ROOT / 'logs/profile-selection-test.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful())
