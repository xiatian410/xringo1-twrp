#!/usr/bin/env python3
"""Bind snapuserd EOF regression to a pinned patch and clean-built packaged daemon."""
import hashlib
import json
from pathlib import Path

from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    index = json.loads((ROOT/'simulation-report.json').read_text())
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-snapuserd-eof.img'
    assert sha(image) == index['image_sha256']
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    build = ROOT/provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    text = build.read_text()
    assert 'Deleted images and staging directories' in text
    assert text.count('build completed successfully') == 2
    assert 'snapuserd clang++ user-space-merge/snapuserd_server.cpp' in text
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/snapuserd-eof-final-source.log').read_text()
    patch = json.loads((TREE/'patches/series.json').read_text())['repositories']['system/core']['patches'][-1]
    assert patch['file'] == '0080-snapuserd-half-close-eof.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    source = str(ANDROID/'system/core/fs_mgr/libsnapshot/snapuserd/user-space-merge/snapuserd_server.cpp')
    old_source = ROOT/'logs/snapuserd-eof-before/snapuserd_server.cpp'
    reports = {}
    for name in ['ota-snapuserd-server', 'ota-snapuserd-server-before']:
        path = ROOT/'logs'/(name+'.json')
        report = json.loads(path.read_text())
        assert report['fixture_elf_machine'] == 183
        assert report['real_server'] and report['real_unix_stream']
        assert not report['kernel_mapping'] and not report['snapshot_handlers']
        assert not report['original_daemon_main']
        for group in ['sources', 'dependencies']:
            for path_name, digest in report[group].items():
                check = old_source if name.endswith('-before') and path_name == source else Path(path_name)
                assert sha(check) == digest, path_name
        cases = {c['name']: c for c in report['cases']}
        assert len(cases) == 8
        fails = {n for n, c in cases.items() if c['status'] == 'FAIL'}
        expected = {'empty-half-close', 'query-then-half-close', 'buffered-query-half-close'} if name.endswith('-before') else set()
        assert fails == expected
        for n, case in cases.items():
            if n in expected:
                assert 'server_wait_status=11' in case['stdout'] and 'signal 11' in case['stderr']
            else:
                assert case['returncode'] == 0 and 'server_wait_status=0 second_query=1 result=PASS' in case['stdout']
        reports[name] = dict(sha256=sha(path), cases=8, failures=len(fails))
    after = json.loads((ROOT/'logs/ota-snapuserd-server.json').read_text())
    before = json.loads((ROOT/'logs/ota-snapuserd-server-before.json').read_text())
    for suffix in ['tests/ota_snapuserd_server.py', 'tests/ota_snapuserd_server.cpp']:
        assert after['sources'][str(ROOT/suffix)] == before['sources'][str(ROOT/suffix)]
    def entries(path):
        return {e[0]: e[-1] for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}
    current = entries(image)
    previous = entries(ROOT/'imgs/built/recovery-dijun-unified-snapshot-unmap.img')
    changed = sorted(n for n in set(current)|set(previous) if current.get(n) != previous.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/snapuserd']
    assert current['system/bin/snapuserd'] == (ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/snapuserd').read_bytes()
    assert b'Empty snapuserd command' in current['system/bin/snapuserd']
    assert b'Empty snapuserd command' not in previous['system/bin/snapuserd']
    package = json.loads(image.with_suffix('.json').read_text())
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    check = next(c for c in index['additional_checks'] if c['name']=='actual-snapuserd-server-eof')
    assert check['evidence_sha256'] == reports['ota-snapuserd-server']['sha256']
    result = dict(status='PASS', scope=__doc__, image=str(image), image_sha256=sha(image),
        production_sources=len(provenance['files']), jobs=provenance['jobs'], reports=reports,
        changed_ramdisk_entries=changed, server_main_replaced=True, real_server_methods=True,
        real_socket_io=True, actual_snapshot_handlers=False, kernel_mapping=False,
        hardware_testing=False, full_ota_install=False)
    (ROOT/'logs/snapuserd-eof-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: actual ARM64 server8, old3 SIGSEGV; pinned0080, clean build',
          len(provenance['files']), 'sources / six profiles; only daemon binary changed')


if __name__ == '__main__':
    main()
