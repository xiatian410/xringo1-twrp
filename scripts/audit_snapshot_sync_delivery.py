#!/usr/bin/env python3
"""Bind SnapshotManager sync failure propagation to clean build and actual ARM64 evidence."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    image = ROOT/'imgs/built/recovery-dijun-unified-snapshot-sync.img'
    prior = ROOT/'imgs/built/recovery-dijun-unified-log-export.img'
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image) and provenance['jobs'] == 30
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    log = ROOT/provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    text = log.read_text()
    assert 'Deleted images and staging directories' in text
    assert text.count('build completed successfully') == 2
    for library in ['libsnapshot_init', 'libsnapshot_nobinder', 'libsnapshot']:
        assert library+' clang++ utility.cpp' in text
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/snapshot-sync-final-source.log').read_text()
    def entries(path):
        return {e[0]: (e[1], e[-1]) for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}
    before, after = entries(prior), entries(image)
    changed = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/fastbootd',
                       'system/bin/init', 'system/bin/recovery', 'system/bin/update_engine_sideload']
    for name in changed[2:]:
        assert after[name][1] == (ANDROID/'out/target/product/O1_asic/recovery/root'/name).read_bytes()
    reports = {}
    for old in [False, True]:
        path = ROOT/('logs/ota-snapshot-finish-before.json' if old else 'logs/ota-snapshot-finish.json')
        report = json.loads(path.read_text())
        assert report['fixture_elf_machine'] == 183 and len(report['cases']) == 16
        assert report['snapshot_manager_executed'] and report['hardware_effects_denied']
        assert report['merge_status_result_boundary'] and not report['full_payload_install']
        assert report['image_sha256'] == sha(image)
        assert bool(report['utility_override']) == old
        for group in ['sources', 'dependencies']:
            for name, digest in report[group].items():
                assert sha(name) == digest, name
        failed = [c['name'] for c in report['cases'] if c['status'] == 'FAIL']
        assert failed == (['boot-sync-error', 'state-sync-error', 'boot-sync-interrupted', 'state-sync-interrupted'] if old else [])
        for case in report['cases']:
            if 'sync-' in case['name']:
                assert 'sync_injections=1' in case['stdout']
            if case['name'] in ['boot-sync-error', 'state-sync-error'] and old:
                assert 'returned=1 expected=0' in case['stdout']
        for name, digest in report['image_entries'].items():
            assert hashlib.sha256(after[name][1]).hexdigest() == digest
        reports[path.name] = dict(sha256=sha(path), cases=16, failed=failed)
    # Existing complete payload evidence is reused only for unchanged actual sources.
    original_sources = {}
    for file in ['ota-stock-payload.json', 'ota-stock-stable-payload.json']:
        report = json.loads((ROOT/'logs'/file).read_text())
        checked = 0
        for name, digest in report['sources'].items():
            if name.startswith(str(ANDROID/'system/update_engine')+'/'):
                assert sha(name) == digest, name
                original_sources[name] = digest
                checked += 1
        assert checked > 0
    package = json.loads(image.with_suffix('.json').read_text())
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    index = json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256'] == sha(image) and index['status'] == 'in_progress'
    assert len(index['not_yet_completed']) == 12
    result = dict(status='PASS', image=str(image), image_sha256=sha(image),
                  production_sources=len(provenance['files']), reports=reports,
                  changed_ramdisk_entries=changed, reused_payload_sources=original_sources,
                  scope=__doc__, hardware_testing=False, full_ota_install=False,
                  power_loss_tested=False, transaction_rollback=False,
                  reused_scope='Unchanged GUI, activation scripts, stock assets and update_engine source; no broad feature reruns. New state-file lifecycle is a separate actual ARM64 execution, not a full payload-plus-mapping integration.')
    (ROOT/'logs/snapshot-sync-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: SnapshotManager 16 cases / two old false-success paths and two missing retries; clean build /',
          len(provenance['files']), 'sources / six profiles; unchanged scope reused')


if __name__ == '__main__':
    main()
