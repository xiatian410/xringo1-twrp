#!/usr/bin/env python3
"""Bind patch0125 PTY ownership, finite regressions and clean delivery."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text())


def entries(p):
    return {e[0]: sha_bytes(e[-1]) for e in ramdisk_entries(boot_parts(Path(p).read_bytes())[1]['ramdisk'])}


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def main():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-terminal-reap.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem+'-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    build = ROOT/provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    assert build.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build.read_text()
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    spec = read(TREE/'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0125-terminal-child-reaping.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    for suffix, count, failures in [('current',7,0),('old',7,6)]:
        path = ROOT/f'logs/terminal-reap-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        reports[suffix] = dict(cases=count, failures=failures, sha256=sha(path))
        assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
        for case in report['cases']:
            if suffix == 'current':
                marker = 'failed_start_fd_closed=1' if case['case'] in ['unlock-failure','fork-failure'] else 'nonblocking_stop_owned_child_reaped=1'
                assert marker in case['output']
            else:
                assert case['status'] == ('PASS' if case['case']=='fork-failure' else 'FAIL')
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-shutdown-admission.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert changed == ['prop.default','ramdisk-files.sha256sum','system/bin/recovery'], changed
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',scope=__doc__,image_sha256=sha(image),production_sources=len(provenance['files']),jobs=provenance['jobs'],reports=reports,changed_ramdisk_entries=changed,
                  limits='Original PTY owner with host PTY/fork/setsid/ioctl/kill/wait/thread; shell exec and syscall faults are fixtures. Direct child only, no descendant/process-group quiescence, full Android shell/GUI/reboot or uninterruptible-child completion proof. No device operations; historical full OTA reused.')
    (ROOT/'logs/terminal-reap-delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: patch0125; PTY7 pass; old6/7 failures; clean image/six profiles')


if __name__ == '__main__':
    main()
