#!/usr/bin/env python3
"""Bind patch0090, finite ARM64 COW initialization checks and clean delivery."""
import json
from pathlib import Path

from audit_snapshot_allocation import sha, read
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def entries(path):
    return {e[0]: e[-1] for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}


def main():
    index = read(ROOT / 'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-snapshot-cow-init.img'
    digest = sha(image)
    assert digest == index['image_sha256']
    provenance = read(image.with_name(image.stem + '-sources.json'))
    assert provenance['image_sha256'] == digest and len(provenance['files']) == 809
    for name, expected in provenance['files'].items():
        assert sha(name) == expected, name
    log = ROOT / provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    assert log.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in log.read_text()
    assert provenance['jobs'] == 30 and 'make -j$(nproc)' in provenance['build_command']
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    spec = read(TREE / 'patches/series.json')['repositories']['system/core']
    patch = spec['patches'][-1]
    assert patch['file'] == '0090-snapshot-cow-initialization-failure.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    source = ANDROID / 'system/core/fs_mgr/libsnapshot/snapshot.cpp'
    previous_source = ROOT / 'logs/snapshot-initialize-before-source/snapshot.cpp'
    assert source.read_text() == previous_source.read_text().replace(
        'if (!writer->Finalize()) {', 'if (!writer || !writer->Finalize()) {', 1)
    assert sha(source) == spec['result_files']['fs_mgr/libsnapshot/snapshot.cpp']
    reports = {}
    for suffix in ['', '-negative']:
        path = ROOT / ('logs/ota-snapshot-initialize' + suffix + '.json')
        r = read(path)
        for mapping in ['sources', 'dependencies']:
            for name, expected in r[mapping].items():
                assert sha(name) == expected, name
        assert r['image_sha256'] == digest and r['fixture_elf_machine'] == 183
        assert r['actual_snapshot_manager'] and r['cow_writer_reader_executed']
        assert r['synthetic_layout'] and r['file_mapping_model']
        assert r['scratch_and_daemon_disabled_for_test']
        assert not r['actual_kernel_mapping'] and not r['full_ota_install']
        assert [c['name'] for c in r['cases']] == ['normal', 'path-error', 'header-sync-error']
        normal, error, sync = r['cases']
        assert normal['status'] == error['status'] == 'PASS'
        assert 'initialized=10 parsed=10 published_lp=1 recreated_completion=1 state=2 hal=1' in normal['stdout']
        assert 'created=2 paths=2 cleanup=1 state=1' in error['stdout']
        assert 'Header sync failed' in sync['stderr']
        if suffix:
            assert r['status'] == sync['status'] == 'FAIL'
            assert sync['returncode'] != 0 and not sync['stdout']
            assert 'Fatal signal 11 (SIGSEGV)' in sync['stderr'] and 'fault addr 0x0' in sync['stderr']
            assert r['snapshot_override'] == str(previous_source)
        else:
            assert r['status'] == sync['status'] == 'PASS' and sync['returncode'] == 0
            assert 'created=2 paths=2 cleanup=1 state=1' in sync['stdout']
            assert 'Could not initialize COW device for odm_dlkm_b' in sync['stderr']
            assert r['snapshot_override'] is None
        entry = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert entry['evidence_sha256'] == sha(path)
        reports[suffix or 'current'] = r
    current, old = reports['current'], reports['-negative']
    assert current['dependencies'] == old['dependencies']
    for name, expected in current['sources'].items():
        if name != str(source):
            assert old['sources'][name] == expected, name
    inventory = ROOT / 'firmware/samples/os4-stable/inventory.json'
    assert current['manifest_sha256'] == old['manifest_sha256'] == sha(inventory.with_name('payload-manifest.pb')) == read(inventory)['manifest_sha256']
    assert current['inventory_sha256'] == old['inventory_sha256'] == sha(inventory)
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-stock-ota-trust.img')
    after = entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/fastbootd',
                       'system/bin/init', 'system/bin/recovery', 'system/bin/update_engine_sideload'], changed
    for name in changed[2:]:
        assert after[name] == (ANDROID / 'out/target/product/O1_asic/recovery/root' / name).read_bytes()
    assert all(sha_bytes(after[name]) == expected
               for name, expected in current['image_entries'].items())
    assert current['image_entries'] == old['image_entries']
    profiles = sorted(p.parent.name for p in (TREE / 'profiles').glob('*/profile.json'))
    assert len(profiles) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', image_sha256=digest, production_sources=809, jobs=30,
                  patch=patch['file'], cases=3, old_failures=1, initialized_and_parsed_cows=10,
                  reports={k: sha(ROOT / ('logs/ota-snapshot-initialize' + ('' if k == 'current' else k) + '.json')) for k in reports},
                  changed_ramdisk_entries=changed, unchanged_profiles=profiles,
                  production_changes=True, new_build=True, full_ota_install=False,
                  scope=__doc__, audit_source_sha256=sha(Path(__file__)))
    (ROOT / 'logs/snapshot-cow-init-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS patch0090 / ARM64 initialization3 / old null crash1 / clean809 / six profiles unchanged')


def sha_bytes(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


if __name__ == '__main__':
    main()
