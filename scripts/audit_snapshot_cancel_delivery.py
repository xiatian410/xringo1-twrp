#!/usr/bin/env python3
"""Bind cancellation error propagation to original ARM64 execution and clean build.

No real mappings, image deletion, merge, slot change or complete OTA claim.
"""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    image = ROOT/'imgs/built/recovery-dijun-unified-snapshot-cancel.img'
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    log = ROOT/provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    text = log.read_text()
    assert 'Deleted images and staging directories' in text
    assert text.count('build completed successfully') == 2
    for library in ['libsnapshot_init', 'libsnapshot_nobinder', 'libsnapshot']:
        assert library+' clang++ snapshot.cpp' in text
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/snapshot-cancel-final-source.log').read_text()
    spec = json.loads((TREE/'patches/series.json').read_text())['repositories']['system/core']
    patch = spec['patches'][-1]
    assert patch['file'] == '0078-snapshot-cancel-cleanup-errors.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']

    def entries(path):
        return {e[0]: (e[1], e[-1]) for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}

    before = entries(ROOT/'imgs/built/recovery-dijun-unified-cli-fifo.img')
    after = entries(image)
    changed = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/fastbootd',
                       'system/bin/init', 'system/bin/recovery', 'system/bin/update_engine_sideload'], changed
    for name in changed[2:]:
        assert after[name][1] == (ANDROID/'out/target/product/O1_asic/recovery/root'/name).read_bytes()
        assert b'Failed to remove update state; cancellation incomplete.' in after[name][1]
    reports = {}
    failures = ['missing-snapshots', 'state-open-error', 'state-sync-error',
                'merge-status-error', 'reset-open-error', 'reset-sync-error']
    for name, count, expected in [('ota-snapshot-cancel', 10, []),
                                  ('ota-snapshot-cancel-before', 10, failures),
                                  ('ota-snapshot-cancel-finish-regression', 16, []),
                                  ('ota-snapshot-cancel-postinstall-regression', 6, [])]:
        path = ROOT/'logs'/f'{name}.json'
        report = json.loads(path.read_text())
        assert report['fixture_elf_machine'] == 183 and len(report['cases']) == count
        assert report['snapshot_manager_executed'] and report['hardware_effects_denied']
        assert not report['full_payload_install'] and report['image_sha256'] == sha(image)
        for group in ['sources', 'dependencies']:
            for source, digest in report[group].items():
                assert sha(source) == digest, source
        failed = [c['name'] for c in report['cases'] if c['status'] == 'FAIL']
        assert failed == expected, name
        if name.startswith('ota-snapshot-cancel') and count == 10:
            assert report['cancellation_executed']
            assert bool(report['snapshot_override']) == bool(expected)
            if expected:
                for case in report['cases']:
                    if case['name'] in expected:
                        assert 'cancelled=1 expected=0' in case['stdout']
            else:
                for case in report['cases']:
                    if case['name'] in failures:
                        assert 'cancelled=0 expected=0' in case['stdout']
                    if case['name'] in ['state-sync-error', 'reset-sync-error', 'state-sync-interrupted']:
                        assert 'sync_errors=1' in case['stdout']
        for entry, digest in report['image_entries'].items():
            assert hashlib.sha256(after[entry][1]).hexdigest() == digest
        reports[name] = dict(sha256=sha(path), cases=count, failed=failed)
    old = json.loads((ROOT/'logs/ota-snapshot-cancel-before.json').read_text())
    new = json.loads((ROOT/'logs/ota-snapshot-cancel.json').read_text())
    for source in [ROOT/'tests/ota_snapshot_finish.py', ROOT/'tests/ota_snapshot_cancel.cpp']:
        assert old['sources'][str(source)] == new['sources'][str(source)]
    reused = {}
    for name in ['ota-stock-payload', 'ota-stock-stable-payload']:
        report = json.loads((ROOT/'logs'/f'{name}.json').read_text())
        matched = {n: h for n, h in report['sources'].items()
                   if n.startswith(str(ANDROID/'system/update_engine')+'/')}
        assert matched
        for source, digest in matched.items():
            assert sha(source) == digest, source
        reused[name] = dict(report_sha256=sha(ROOT/'logs'/f'{name}.json'), unchanged_engine_sources=len(matched))
    package = json.loads(image.with_suffix('.json').read_text())
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    index = json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256'] == sha(image) and index['status'] == 'in_progress'
    assert len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image=str(image), image_sha256=sha(image),
                  production_sources=len(provenance['files']), jobs=provenance['jobs'],
                  reports=reports, changed_ramdisk_entries=changed, reused_payload_sources=reused,
                  hardware_testing=False, full_ota_install=False, actual_mapping=False,
                  transaction_rollback=False, actual_snapshot_deletion=False)
    (ROOT/'logs/snapshot-cancel-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: cancellation10 / old6 false-success cases; completion16 / postinstall6;',
          len(provenance['files']), 'clean-build sources / six profiles; hardware denied')


if __name__ == '__main__':
    main()
