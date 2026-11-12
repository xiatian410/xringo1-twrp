#!/usr/bin/env python3
"""Bind MTP Reset tests to the final built image without asserting USB hardware."""
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


def bindings(report):
    for group in ['sources', 'test_sources', 'shared_sources']:
        for name, digest in report.get(group, {}).items():
            assert sha(ROOT / name) == digest, name


def main():
    index = read('simulation-report.json')
    image = Path(index['image'])
    digest = sha(image)
    assert image.name == 'recovery-dijun-unified-mtp-reset.img' and digest == index['image_sha256']
    evidence = []
    for label, count in [('control', 80), ('server', 78), ('transfers', 48), ('events', 62)]:
        name = 'logs/mtp-reset-' + label + '.json'
        report = read(name)
        bindings(report)
        assert report['status'] == 'PASS' and len(report['cases']) == count
        assert all(c['status'] == 'PASS' for c in report['cases'])
        evidence.append(name)
    old_control = read('logs/mtp-reset-control-before.json')
    old_server = read('logs/mtp-reset-server-before.json')
    for report, total, failed in [(old_control, 80, {'reset-session-signal', 'reset-status-busy', 'reset-clears-cancel'}),
                                  (old_server, 10, {'reset-idle', 'reset-pending-new', 'reset-pending-overwrite',
                                                   'reset-data-in', 'reset-data-out', 'reset-response', 'reset-receive', 'reset-send', 'reset-edit'})]:
        bindings(report)
        assert report['status'] == 'FAIL' and len(report['cases']) == total
        assert {c['case'] for c in report['cases'] if c['status'] != 'PASS'} == failed
        assert all(c['returncode'] == 1 and 'FAIL ' in c['output'] for c in report['cases'] if c['status'] != 'PASS')
    assert old_control['test_sources'] == read('logs/mtp-reset-control.json')['test_sources']
    assert old_server['test_sources'] == read('logs/mtp-reset-server.json')['test_sources']
    evidence += ['logs/mtp-reset-control-before.json', 'logs/mtp-reset-server-before.json']
    transport = read('logs/mtp-reset-transport.json')
    bindings(transport)
    assert transport['status'] == 'PASS' and transport['returncode'] == 0
    evidence.append('logs/mtp-reset-transport.json')
    provenance = json.loads(image.with_name(image.stem + '-sources.json').read_text())
    assert provenance['jobs'] == 30 and provenance['image_sha256'] == digest
    assert len(provenance['files']) == 735
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
    previous = read('imgs/built/recovery-dijun-unified-mtp-transaction.json')
    assert [n for n, h in previous['binary_hashes'].items() if meta['binary_hashes'][n] != h] == ['system/lib64/libtwrpmtp-ffs.so']
    runtime = read('logs/mtp-reset-profile-runtime-image.json')
    bindings(runtime)
    assert runtime['status'] == 'PASS' and runtime['image_sha256'] == digest
    assert runtime['tests_run'] == 9 and len(runtime['cases']) == 102
    evidence.append('logs/mtp-reset-profile-runtime-image.json')
    for name in evidence:
        check, = [c for c in index['checks'] if c['evidence'] == name]
        assert check['evidence_sha256'] == sha(ROOT / name)
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=digest, production_source_files=735,
                  control_cases=80, server_cases=78, old_control_failures=3, old_reset_server_failures=9,
                  transfers=48, events=62, profile_groups=9, profile_calls=102,
                  field_vibration='unresolved', field_settings='unresolved',
                  evidence={n: sha(ROOT / n) for n in evidence},
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md', 'MAINTENANCE.md',
                             'simulation-report.md', 'simulation-report.json', 'docs/MTP-CONTROL-ADAPTATION.md']},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/mtp-reset-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: Reset control80/server78(old3/9 failures), transfers48/events62, profile9/102,735 source files; hardware unresolved')


if __name__ == '__main__':
    main()
