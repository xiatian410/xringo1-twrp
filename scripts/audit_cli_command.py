#!/usr/bin/env python3
"""Bind CLI command bounds and reused unchanged listener evidence to delivery."""
import json
from pathlib import Path
from audit_terminal_reap import entries, read, sha
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def main():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-cli-command.img'
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
    patch = read(TREE/'patches/series.json')['repositories']['bootable/recovery']['patches'][-1]
    assert patch['file'] == '0136-cli-command-bounds.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    for suffix, failures in [('current',0),('old',5)]:
        path = ROOT/f'logs/cli-command-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == 12
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        if suffix=='current':
            assert all('cli_exact_zero_padded_record_or_reject_before_fifo=1' in c['output'] for c in report['cases'])
            assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
        else:
            assert all('AddressSanitizer: stack-buffer-overflow' in c['output'] for c in report['cases'] if c['status']=='FAIL')
        reports[suffix] = dict(cases=12,failures=failures,sha256=sha(path))
    reused = ROOT/'logs/shutdown-admission-cli.json'
    listener = read(reused)
    assert listener['status']=='PASS' and len(listener['cases'])==16
    for name, digest in listener['sources'].items():
        assert sha(name) == digest, name
    reports['unchanged-listener-reused'] = dict(cases=16,sha256=sha(reused))
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-ors-reboot.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert changed == ['prop.default','ramdisk-files.sha256sum','system/bin/twrp'], changed
    from firmware_facts import boot_parts, ramdisk_entries
    packaged = {e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    assert b'Command exceeds %zu bytes.' in packaged['system/bin/twrp']
    assert packaged['system/bin/twrp'] == (ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/twrp').read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256']==sha(image) and len(package['profiles'])==6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',image_sha256=sha(image),production_sources=len(provenance['files']),jobs=provenance['jobs'],reports=reports,changed_ramdisk_entries=changed,
        limits='Original client main on host ASan/UBSan; FIFO/capability/help sinks are fixtures. Exact record and zero padding checked. Unchanged listener evidence reused after every source binding matched. No full client/server/ORS joined execution, ARM64 runtime, physical device or complete shutdown proof. Historical OTA reused.')
    (ROOT/'logs/cli-command-delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: patch0136; client12/old5 overflow failures; unchanged listener16 reused; clean image/six profiles')


if __name__ == '__main__':
    main()
