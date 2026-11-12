#!/usr/bin/env python3
"""Check the clock-failure delivery checkpoint; not a full task acceptance audit."""
import hashlib
import json
from pathlib import Path

from firmware_facts import boot_parts, ramdisk_entries

ROOT = Path(__file__).resolve().parents[1]
ANDROID = Path('/root/AAA/twrp')
IMAGE = ROOT / 'imgs/built/recovery-dijun-unified-clock-failure.img'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(name):
    return json.loads((ROOT / name).read_text())


def main():
    expected = '1c0813cf324d76be52e588e4dd3358c1c104946841e393aef84df2d951437adc'
    assert sha(IMAGE) == expected
    provenance = json.loads(IMAGE.with_name(IMAGE.stem + '-sources.json').read_text())
    assert provenance['image_sha256'] == expected and len(provenance['files']) == 712
    for name, digest in provenance['files'].items():
        assert sha(Path(name)) == digest, name
    for name, target in provenance['symlinks'].items():
        assert Path(name).is_symlink() and str(Path(name).readlink()) == target, name
    assert sha(ROOT / provenance['build_log']) == provenance['build_log_sha256']
    evidence = []
    for name, count in [('logs/clock-failure-status-regression.json', 28),
                        ('logs/clock-failure-settings-regression.json', 21),
                        ('logs/filesystem-tools-image-test.json', 17)]:
        report = load(name)
        assert report['status'] == 'PASS' and len(report['cases']) == count
        for source, digest in report['sources'].items():
            p = Path(source) if source.startswith('/') else ANDROID / 'bootable/recovery' / source
            assert sha(p) == digest, (name, source)
        for source, digest in report.get('test_sources', {}).items():
            p = Path(source) if source.startswith('/') else ROOT / 'tests' / source
            assert sha(p) == digest, (name, source)
        evidence.append(name)
    before = load('logs/clock-failure-status-before.json')
    assert [c['case'] for c in before['cases'] if c['status'] == 'FAIL'] == [
        'clock-read-error', 'clock-conversion-error', 'clock-error-recovery']
    evidence.append('logs/clock-failure-status-before.json')
    runtime = load('logs/clock-failure-profile-runtime.json')
    assert runtime['status'] == 'PASS' and runtime['tests_run'] == 9
    assert runtime['image_sha256'] == expected and len(runtime['cases']) == 102
    for name, digest in {**runtime['sources'], **runtime['test_sources']}.items():
        path = Path(name) if name.startswith('/') else ROOT / name
        assert sha(path) == digest, name
    evidence.append('logs/clock-failure-profile-runtime.json')
    metadata = json.loads(IMAGE.with_suffix('.json').read_text())
    assert metadata['sha256'] == expected
    assert metadata['status_build_configuration']['qcom_rtc_fix'] is False
    _, parts = boot_parts(IMAGE.read_bytes())
    entries = {e[0]: e[-1] for e in ramdisk_entries(parts['ramdisk'])}
    for name, digest in metadata['binary_hashes'].items():
        assert hashlib.sha256(entries[name]).hexdigest() == digest, name
    for name, digest in load('logs/filesystem-tools-image-test.json')['ramdisk_files'].items():
        assert hashlib.sha256(entries[name]).hexdigest() == digest, name
    docs = ['ADAPTATION-GOALS.md', 'simulation-report.json', 'simulation-report.md',
            'compatibility-matrix.md', 'FEATURE-USAGE.md', 'MAINTENANCE.md',
            'docs/STATUS-ADAPTATION.md',
            'docs/FILESYSTEM-TOOLS-EXECUTION.md']
    report = dict(status='PASS', scope=__doc__, image_sha256=expected, sources=712,
                  state_cases=28, settings_cases=21, filesystem_cases=17,
                  runtime_groups=9, runtime_phase_calls=102,
                  evidence={n: sha(ROOT / n) for n in evidence},
                  documentation={n: sha(ROOT / n) for n in docs},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/clock-failure-delivery.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: clock failure delivery inputs/image/regressions; whole goal remains incomplete')


if __name__ == '__main__':
    main()
