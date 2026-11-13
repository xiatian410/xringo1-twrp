#!/usr/bin/env python3
"""Bind unmap error propagation to original ARM64 execution and clean build.

Original verifier and controller with mapping result doubles; no real mappings,
image deletion, merge, slot change or complete OTA claim.
"""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    image = ROOT/'imgs/built/recovery-dijun-unified-snapshot-unmap.img'
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    log = ROOT/provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    text = log.read_text()
    assert 'Deleted images and staging directories' in text
    assert text.count('build completed successfully') == 2
    for library in ['libupdate_engine_boot_control', 'libpayload_consumer']:
        assert library+' clang++ '+('aosp/dynamic_partition_control_android.cc' if library == 'libupdate_engine_boot_control' else 'payload_consumer/filesystem_verifier_action.cc') in text
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/snapshot-unmap-final-source.log').read_text()
    spec = json.loads((TREE/'patches/series.json').read_text())['repositories']['system/update_engine']
    patch = spec['patches'][-1]
    assert patch['file'] == '0079-snapshot-unmap-error-propagation.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']

    def entries(path):
        return {e[0]: (e[1], e[-1]) for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}

    before = entries(ROOT/'imgs/built/recovery-dijun-unified-snapshot-cancel.img')
    after = entries(image)
    changed = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/update_engine_sideload'], changed
    binary = after['system/bin/update_engine_sideload'][1]
    assert binary == (ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/update_engine_sideload').read_bytes()
    assert b'Failed to unmap snapshot partitions before remapping' in binary
    assert b'Failed to unmap snapshot partitions after verification' in binary
    reports = {}
    expected_reports = [
        ('ota-snapshot-unmap-verifier', 9, []),
        ('ota-snapshot-unmap-verifier-before', 9, ['cleanup-fail', 'remap-unmap-fail']),
        ('ota-unmap-control', 8, []),
        ('ota-unmap-control-before', 8, ['snapshot-fail', 'logical-fail', 'combined-fail', 'empty', 'non-vab', 'no-metadata']),
        ('ota-snapshot-unmap-cancel-regression', 10, []),
        ('ota-snapshot-unmap-postinstall-regression', 6, []),
    ]
    for name, count, expected in expected_reports:
        path = ROOT/'logs'/f'{name}.json'
        report = json.loads(path.read_text())
        assert report['fixture_elf_machine'] == 183 and len(report['cases']) == count
        assert not report['full_payload_install'] and report['image_sha256'] == sha(image)
        for group in ['sources', 'dependencies']:
            for source, digest in report[group].items():
                assert sha(source) == digest, source
        failed = [c['name'] for c in report['cases'] if c['status'] == 'FAIL']
        assert failed == expected, name
        for entry, digest in report['image_entries'].items():
            assert hashlib.sha256(after[entry][1]).hexdigest() == digest
        reports[name] = dict(sha256=sha(path), cases=count, failed=failed)
    verifier = json.loads((ROOT/'logs/ota-snapshot-unmap-verifier.json').read_text())
    cases = {c['name']: c for c in verifier['cases']}
    assert 'code=47 map=0 unmap=1' in cases['remap-unmap-fail']['stdout']
    assert 'code=47 map=1 unmap=1' in cases['cleanup-fail']['stdout']
    assert 'code=15' in cases['hash-mismatch-unmap-fail']['stdout']
    control = json.loads((ROOT/'logs/ota-unmap-control.json').read_text())
    cases = {c['name']: c for c in control['cases']}
    for name in ['snapshot-fail', 'logical-fail', 'combined-fail']:
        assert 'result=0 expected=0 snapshots=1 attempts=2' in cases[name]['stdout']
    for name in ['non-vab', 'no-metadata']:
        assert 'snapshots=0 attempts=2' in cases[name]['stdout']
    for stem, fixture, script in [('ota-snapshot-unmap-verifier', 'ota_snapshot_map.cpp', 'ota_snapshot_map.py'),
                                  ('ota-unmap-control', 'ota_unmap_control.cpp', 'ota_unmap_control.py')]:
        old = json.loads((ROOT/'logs'/f'{stem}-before.json').read_text())
        new = json.loads((ROOT/'logs'/f'{stem}.json').read_text())
        for file in [fixture, script]:
            key = str(ROOT/'tests'/file)
            assert old['sources'][key] == new['sources'][key]
    # Do not rerun stock payloads merely because the verifier/controller changed.
    # Reuse only unchanged executor sources; changed stages have current tests above.
    reused = {}
    for name in ['ota-stock-payload', 'ota-stock-stable-payload']:
        report = json.loads((ROOT/'logs'/f'{name}.json').read_text())
        matched = {n: h for n, h in report['sources'].items()
                   if n.startswith(str(ANDROID/'system/update_engine')+'/') and
                   Path(n).name not in {'filesystem_verifier_action.cc', 'dynamic_partition_control_android.cc'}}
        assert matched
        for source, digest in matched.items():
            assert sha(source) == digest, source
        reused[name] = dict(report_sha256=sha(ROOT/'logs'/f'{name}.json'), unchanged_sources=len(matched),
                            scope='Only unchanged executor sources; not whole current OTA integration')
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
    (ROOT/'logs/snapshot-unmap-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: verifier9 / old2; controller8 / old6; cancel10 / postinstall6;',
          len(provenance['files']), 'clean-build sources / six profiles; no real mapping')


if __name__ == '__main__':
    main()
