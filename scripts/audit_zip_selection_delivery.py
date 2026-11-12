#!/usr/bin/env python3
"""Bind ZIP selection, actual host install chain and clean image provenance.

Host ZIP/verifier/digest/fork/exec run in private chroots. Property, mount and
UI sinks are fixtures; ABI-named binaries contain host code. This is neither
an ARM updater, AB payload, GUI/sideload nor physical-device acceptance test.
"""
import hashlib
import json
import os
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def bindings(values):
    for name, expected in values.items():
        assert sha(ROOT / name) == expected, name


def main():
    index = read('simulation-report.json')
    image = Path(index['image'])
    digest = sha(image)
    assert image.name == 'recovery-dijun-unified-zip-selection.img'
    assert index['image_sha256'] == digest
    provenance = read(image.with_name(image.stem + '-sources.json'))
    bindings(provenance['files'])
    assert provenance['image_sha256'] == digest and len(provenance['files']) == 750
    assert provenance['jobs'] == 30
    assert provenance['build_command'] == 'make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
    for name, target in provenance['symlinks'].items():
        assert os.readlink(name) == target
    log = ROOT / provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    assert log.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in log.read_text()
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (
        ROOT / 'logs/zip-selection-final-source-recheck.log').read_text()

    previous = ROOT / 'imgs/built/recovery-dijun-unified-updater-protocol.img'
    prior = read(previous.with_name(previous.stem + '-sources.json'))
    assert sha(previous) == prior['image_sha256']
    changed = {name for name, value in provenance['files'].items() if prior['files'].get(name) != value}
    assert changed == {
        str(ANDROID / 'bootable/recovery/twrpinstall/twinstall.cpp'),
        str(ANDROID / 'device/xiaomi/O1_asic/patches/0053-zip-updater-abi-selection.patch'),
        str(ANDROID / 'device/xiaomi/O1_asic/patches/series.json')}
    assert not set(prior['files']) - set(provenance['files'])
    saved = ROOT / 'logs/zip-install-before/twinstall.cpp'
    assert sha(saved) == prior['files'][str(ANDROID / 'bootable/recovery/twrpinstall/twinstall.cpp')]

    evidence = ['logs/zip-install-chain.json', 'logs/zip-install-chain-before.json',
                'logs/zip-selection-updater-regression.json', 'logs/image-install-chain.json',
                'logs/zip-selection-profile-runtime.json', 'logs/zip-selection-module-state.json']
    reports = [read(name) for name in evidence]
    for name, report in zip(evidence, reports):
        assert report['status'] == ('FAIL' if name.endswith('before.json') else 'PASS'), name
        for key in ['sources', 'tests', 'test_sources', 'binary_dependencies']:
            bindings(report.get(key, {}))
    current, before, updater, routes, profile, modules = reports
    assert len(current['cases']) == len(before['cases']) == 36
    failures = {c['case'] for c in before['cases'] if c['status'] == 'FAIL'}
    assert failures == {'arch-first', 'arch-second', 'arch-abi-property',
                        'arch-both', 'arch-reversed', 'arch-empty-fallback'}
    assert [c['case'] for c in current['cases']] == [c['case'] for c in before['cases']]
    for name in ['tests/zip_install_chain_test.py', 'tests/zip_install_chain_test.cpp',
                 'tests/zip_install_fixture.cpp', 'tests/nested_partition_path_test.py']:
        assert current['sources'][str(ROOT / name)] == before['sources'][str(ROOT / name)]
    # Library/source dependencies, except the saved installer under test, match.
    assert {p: h for p, h in current['sources'].items() if not p.endswith('/twinstall.cpp')} == {
        p: h for p, h in before['sources'].items() if not p.endswith('/twinstall.cpp')}
    assert current['binary_dependencies'] == before['binary_dependencies']
    rows = {c['case']: c for c in current['cases']}
    for row in rows.values():
        assert row['exit'] == 0 and row['content_ok'] and row['contexts_ok']
    for name, tag in [('arch-both', 'arm64'), ('arch-reversed', 'arm32'),
                      ('generic-priority', 'generic'), ('arch-empty-fallback', 'arm64'),
                      ('generic-no-properties', 'generic')]:
        assert rows[name]['result_tag'] == tag
    assert 'whole-file signature verified against RSA key 0' in rows['signed-correct']['output']
    for name in ['signed-wrong-key', 'signed-tampered', 'unsigned-required']:
        assert 'Zip signature verification failed' in rows[name]['output']
    for name in ['digest-bad', 'digest-malformed', 'digest-wrong-name']:
        assert 'Aborting zip install: Digest verification failed' in rows[name]['output']
    assert len(updater['cases']) == 22 and all(c['exit'] == 0 for c in updater['cases'])
    assert len(routes['cases']) == 40
    assert all(c['exit'] == 0 and c['content_ok'] and c['order_ok'] for c in routes['cases'])
    for report, groups, calls in [(profile, 9, 102), (modules, 4, 24)]:
        assert report['image_sha256'] == digest and report['tests_run'] == groups
        assert len(report['cases']) == calls and all(c['actual'] == c['expected'] for c in report['cases'])

    metadata = read(image.with_suffix('.json'))
    old_metadata = read(previous.with_suffix('.json'))
    assert metadata['sha256'] == digest and len(metadata['profiles']) == 6
    entries = {e[0]: e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for name, expected in metadata['binary_hashes'].items():
        assert hashlib.sha256(entries[name]).hexdigest() == expected
    for name in ['system/lib64/libgui2.so', 'system/lib64/libtwrpminui.so', 'system/lib64/libtwrpmtp-ffs.so']:
        assert metadata['binary_hashes'][name] == old_metadata['binary_hashes'][name]
    assert b'Zip contains no updater for the advertised ABIs' in entries['system/bin/recovery']
    # Screenshot fix remains in the source series; no new GUI/discovery changes.
    spec = read(TREE / 'patches/series.json')['repositories']['bootable/recovery']
    for name in ['sysfs_device_match.hpp', 'gui2/backend/mount_backend.h']:
        assert spec['result_files'][name] == prior['files'][str(ANDROID / 'bootable/recovery' / name)]
    assert any(p['file'] == '0048-otg-controller-discovery.patch' for p in spec['patches'])
    for name in evidence:
        checks = [c for c in index['additional_checks'] if c.get('evidence') == name]
        assert checks and all(c['evidence_sha256'] == sha(ROOT / name) for c in checks)
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    docs = ['ADAPTATION-GOALS.md', 'MAINTENANCE.md', 'FEATURE-USAGE.md', 'simulation-report.md',
            'simulation-report.json', 'docs/INSTALL-CHAIN-VALIDATION.md', 'docs/MOUNT-LIST-EXPLANATION.md']
    result = dict(status='PASS', scope=__doc__, image=str(image), image_sha256=digest,
                  production_sources=750, zip_cases=36, old_failures=6, updater_cases=22,
                  image_route_cases=40, profile_groups=9, module_groups=4,
                  evidence={p: sha(ROOT / p) for p in evidence},
                  documents={p: sha(ROOT / p) for p in docs}, audit_source_sha256=sha(Path(__file__)),
                  limitations='Native host ZIP chain only; ARM execution, full GUI/backend queue, '
                              'AB payload/update_engine, sideload and physical hardware remain unverified. '
                              'Focused audit does not repair all historical full-audit source drift.')
    (ROOT / 'logs/zip-selection-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: ZIP36/old6 failures;updater22;image-route40;750 sources;profile9/module4. Full goal in progress.')


if __name__ == '__main__':
    main()
