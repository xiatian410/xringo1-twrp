#!/usr/bin/env python3
"""Check transaction-cancel software evidence and its actual image, not hardware."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import manifest, TREE, ANDROID

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((ROOT / name).read_text())


def sources(report):
    for group in ('sources', 'test_sources', 'shared_sources'):
        for name, digest in report.get(group, {}).items():
            assert sha(ROOT / name) == digest, name


def main():
    index = read('simulation-report.json')
    image = Path(index['image'])
    digest = sha(image)
    assert image.name == 'recovery-dijun-unified-mtp-transaction.img'
    assert index['image_sha256'] == digest
    counts = {'control': 73, 'server': 68, 'transfers': 48, 'events': 62}
    evidence = []
    for name, count in counts.items():
        path = 'logs/mtp-transaction-' + name + '.json'
        report = read(path)
        sources(report)
        assert report['status'] == 'PASS' and len(report['cases']) == count
        assert all(c['status'] == 'PASS' for c in report['cases'])
        evidence.append(path)
    before = read('logs/mtp-transaction-control-before.json')
    sources(before)
    assert before['status'] == 'FAIL' and len(before['cases']) == 73
    failed = {c['case'] for c in before['cases'] if c['status'] == 'FAIL'}
    assert failed == {'transaction-idle', 'transaction-mismatch', 'transaction-finished',
                      'transaction-next-command', 'transaction-max-mismatch'}
    assert all(c['returncode'] == 1 and 'FAIL ' in c['output']
               for c in before['cases'] if c['status'] == 'FAIL')
    assert before['test_sources'] == read('logs/mtp-transaction-control.json')['test_sources']
    transport = read('logs/mtp-transaction-transport.json')
    sources(transport)
    assert transport['status'] == 'PASS' and transport['returncode'] == 0
    evidence += ['logs/mtp-transaction-control-before.json', 'logs/mtp-transaction-transport.json']
    provenance = json.loads(image.with_name(image.stem + '-sources.json').read_text())
    assert provenance['image_sha256'] == digest and provenance['jobs'] == 30
    assert len(provenance['files']) == 734
    for name, expected in provenance['files'].items():
        assert sha(Path(name)) == expected, name
    for name, target in provenance['symlinks'].items():
        assert str(Path(name).readlink()) == target, name
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    log = ROOT / provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    assert log.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in log.read_text()
    meta = json.loads(image.with_suffix('.json').read_text())
    assert meta['sha256'] == digest and len(meta['profiles']) == 6
    entries = {e[0]: e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for name, expected in meta['binary_hashes'].items():
        assert hashlib.sha256(entries[name]).hexdigest() == expected, name
    previous = read('imgs/built/recovery-dijun-unified-haptics-probe.json')
    assert [n for n, h in previous['binary_hashes'].items()
            if meta['binary_hashes'][n] != h] == ['system/lib64/libtwrpmtp-ffs.so']
    runtime_path = 'logs/mtp-transaction-profile-runtime-image.json'
    runtime = read(runtime_path)
    sources(runtime)
    assert runtime['status'] == 'PASS' and runtime['image_sha256'] == digest
    assert runtime['tests_run'] == 9 and len(runtime['cases']) == 102
    evidence.append(runtime_path)
    for name in evidence:
        check, = [c for c in index['checks'] if c['evidence'] == name]
        assert check['evidence_sha256'] == sha(ROOT / name)
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    assert 'Pending: 0 source updates, device tree changed=False' in (
        ROOT / 'logs/mtp-transaction-final-source-recheck.log').read_text()
    result = dict(status='PASS', scope=__doc__, image_sha256=digest,
                  source_files=734, control_cases=73, old_failures=5,
                  server_cases=68, transfer_cases=48, event_cases=62,
                  profile_groups=9, profile_calls=102, physical_vibration='unverified',
                  evidence={name: sha(ROOT / name) for name in evidence},
                  documents={name: sha(ROOT / name) for name in (
                      'ADAPTATION-GOALS.md', 'MAINTENANCE.md', 'simulation-report.json',
                      'simulation-report.md', 'docs/MTP-TRANSACTION-CANCEL.md')},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/mtp-transaction-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: control73/old5 failures/server68/transfers48/events62; 734 sources/profile9/102; hardware unresolved')


if __name__ == '__main__':
    main()
