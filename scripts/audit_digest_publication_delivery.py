#!/usr/bin/env python3
"""Bind atomic digest checks to the built candidate; not a full-goal audit."""
import hashlib
import json
from pathlib import Path

from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(name):
    return json.loads((ROOT / name).read_text())


def bindings(report):
    for group in ['sources', 'shared_sources', 'test_sources', 'tests']:
        for name, digest in report.get(group, {}).items():
            assert sha(ROOT / name) == digest, name


def main():
    index = read('simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-digest-atomic.img'
    digest = sha(image)
    assert digest == index['image_sha256']
    evidence = []
    current = read('logs/digest-publication.json')
    old = read('logs/digest-publication-before.json')
    for report in [current, old]:
        bindings(report)
        assert len(report['cases']) == 54
        assert {c['algorithm'] for c in report['cases']} == {'md5', 'sha256'}
    assert current['status'] == 'PASS' and all(c['status'] == 'PASS' for c in current['cases'])
    assert old['status'] == 'FAIL'
    assert old['test_sources'] == current['test_sources']
    assert sum(c['status'] == 'FAIL' for c in old['cases']) == 44
    old_passes = {'target-dir', 'source-missing', 'split-normal', 'caller-normal', 'caller-cancel-after-digest'}
    for algorithm in ['md5', 'sha256']:
        assert {c['case'] for c in old['cases'] if c['algorithm'] == algorithm and c['status'] == 'PASS'} == old_passes
        for case in old['cases']:
            if case['algorithm'] == algorithm and case['status'] == 'FAIL':
                assert case['returncode'] == 1 and 'FAIL line ' in case['output']
    evidence += ['logs/digest-publication.json', 'logs/digest-publication-before.json']
    for name, count in [('digest-atomic-restore', 54), ('digest-atomic-backup', 55)]:
        report = read('logs/' + name + '.json')
        bindings(report)
        assert report['status'] == 'PASS' and len(report['cases']) == count
        assert all(c['status'] == 'PASS' for c in report['cases'])
        evidence.append('logs/' + name + '.json')
    for name, count, calls in [('profile-runtime', 9, 102), ('module-state', 4, 24)]:
        report = read('logs/digest-atomic-' + name + '.json')
        bindings(report)
        assert report['status'] == 'PASS' and report['image_sha256'] == digest
        assert report['tests_run'] == count and len(report['cases']) == calls
        assert all(c['actual'] == c['expected'] for c in report['cases'])
        evidence.append('logs/digest-atomic-' + name + '.json')
    for name, count in [('haptics-policy', 12), ('usb-policy', 53), ('init', 5)]:
        report = read('logs/digest-atomic-' + name + '.json')
        bindings(report)
        assert report.get('status', report.get('result')) == 'PASS'
        assert report['image_sha256'] == digest and len(report['checks']) == count
        evidence.append('logs/digest-atomic-' + name + '.json')
    provenance = json.loads(image.with_name(image.stem + '-sources.json').read_text())
    assert provenance['jobs'] == 30 and provenance['image_sha256'] == digest
    assert len(provenance['files']) == 736
    for name, expected in provenance['files'].items():
        assert sha(name) == expected, name
    for name, target in provenance['symlinks'].items():
        assert str(Path(name).readlink()) == target, name
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    log = ROOT / provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    assert log.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in log.read_text()
    meta = json.loads(image.with_suffix('.json').read_text())
    assert meta['sha256'] == digest and len(meta['profiles']) == 6 and meta['digest_atomic_publication_compiled']
    previous = read('imgs/built/recovery-dijun-unified-mtp-reset.json')
    assert meta['profiles'] == previous['profiles'] and meta['unique_blobs'] == previous['unique_blobs'] == 78
    assert [name for name, value in meta['binary_hashes'].items() if previous['binary_hashes'][name] != value] == ['system/bin/recovery']
    entries = {e[0]: e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for name, expected in meta['binary_hashes'].items():
        assert hashlib.sha256(entries[name]).hexdigest() == expected, name
    for marker in [b'Digest %s failed for', b'Digest replaced but directory sync failed', b'.twrp-digest.XXXXXX']:
        assert marker in entries['system/bin/recovery']
    for name in evidence:
        check, = [c for c in index['checks'] if c['evidence'] == name]
        assert check['evidence_sha256'] == sha(ROOT / name), name
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=digest, production_source_files=736,
                  digest_cases=54, negative_control_failures=44, restore_cases=54, backup_cases=55,
                  profile_groups=9, profile_calls=102, module_groups=4, module_calls=24,
                  field_vibration='unresolved', field_settings='unresolved', field_touch='unresolved',
                  full_goal='in_progress', outstanding_groups=12, evidence={n: sha(ROOT / n) for n in evidence},
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md', 'MAINTENANCE.md',
                             'simulation-report.md', 'simulation-report.json', 'docs/BACKUP-SESSION-ADAPTATION.md', 'FEATURE-USAGE.md',
                             'docs/HAPTICS-ADAPTATION.md']},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/digest-atomic-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: digest54/old44 failures, restore54/backup55, current-image profile9/102/modules4/24/policy12+53/init5,736 production sources; physical faults unresolved')


if __name__ == '__main__':
    main()
