#!/usr/bin/env python3
"""Bind CLI command bounds and reused unchanged listener evidence to delivery."""
import json
import argparse
from pathlib import Path
from audit_terminal_reap import entries, read, sha
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', action='store_true')
    args = parser.parse_args()
    output_mode = args.output
    batch = 'cli-output' if output_mode else 'cli-command'
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == f'recovery-dijun-unified-{batch}.img'
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
    assert patch['file'] == ('0137-cli-output-byte-count.patch' if output_mode else '0136-cli-command-bounds.patch')
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    expected = [('joined-current',13,0),('joined-old',13,6),('io-current',7,0),('io-old',7,6),('assembly',12,0)] if output_mode else [('current',12,0),('old',12,5)]
    for suffix, count, failures in expected:
        path = ROOT/f'logs/{batch}-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        if output_mode:
            if failures==0:
                assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
            if suffix.startswith('joined'):
                assert all(c['listener_returncode']==0 and c['client_returncode']==0 for c in report['cases'])
                bad = {f'output-{n}' for n in [510,511,512,513,1024,2049]}
                assert all(c['status']==('FAIL' if suffix=='joined-old' and c['case'] in bad else 'PASS') for c in report['cases'])
                assert all((c['output_sha256']==c['expected_sha256'])==(c['status']=='PASS') for c in report['cases'])
            if suffix=='io-current':
                assert all('cli_output_error_propagation_and_exact_bytes=1' in c['output'] for c in report['cases'])
        elif suffix=='current':
            assert all('cli_exact_zero_padded_record_or_reject_before_fifo=1' in c['output'] for c in report['cases'])
            assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
        else:
            assert all('AddressSanitizer: stack-buffer-overflow' in c['output'] for c in report['cases'] if c['status']=='FAIL')
        reports[suffix] = dict(cases=count,failures=failures,sha256=sha(path))
    reused = ROOT/'logs/shutdown-admission-cli.json'
    listener = read(reused)
    assert listener['status']=='PASS' and len(listener['cases'])==16
    for name, digest in listener['sources'].items():
        assert sha(name) == digest, name
    reports['unchanged-listener-reused'] = dict(cases=16,sha256=sha(reused))
    before = entries(ROOT/('imgs/built/recovery-dijun-unified-cli-command.img' if output_mode else 'imgs/built/recovery-dijun-unified-ors-reboot.img'))
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert changed == ['prop.default','ramdisk-files.sha256sum','system/bin/twrp'], changed
    from firmware_facts import boot_parts, ramdisk_entries
    packaged = {e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    assert b'Command exceeds %zu bytes.' in packaged['system/bin/twrp']
    if output_mode:assert b'Error reading command output: %s' in packaged['system/bin/twrp']
    assert packaged['system/bin/twrp'] == (ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/twrp').read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256']==sha(image) and len(package['profiles'])==6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',image_sha256=sha(image),production_sources=len(provenance['files']),jobs=provenance['jobs'],reports=reports,changed_ramdisk_entries=changed,
        limits=('Original client/listener joined using private host FIFO/process/stdio/executor; ORS body/settings/console/partition are fixtures. Separate I/O faults injected at syscalls/stdio. No full ORS execution/exit status, ARM64 runtime, FIFO liveness bound, physical device or complete shutdown proof. Historical OTA reused.' if output_mode else 'Original client main on host ASan/UBSan; FIFO/capability/help sinks are fixtures. Exact record and zero padding checked. Unchanged listener evidence reused after every source binding matched. No full client/server/ORS joined execution, ARM64 runtime, physical device or complete shutdown proof. Historical OTA reused.'))
    (ROOT/f'logs/{batch}-delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS:',batch,reports,'clean image/six profiles')


if __name__ == '__main__':
    main()
