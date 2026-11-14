#!/usr/bin/env python3
"""Bind ORS command, startup, staging or missing-argument fixes to a clean delivery."""
import argparse
import json
from pathlib import Path
from audit_terminal_reap import entries, read, sha
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--sequence', action='store_true')
    modes.add_argument('--staging', action='store_true')
    modes.add_argument('--arguments', action='store_true')
    modes.add_argument('--input', action='store_true')
    args = parser.parse_args()
    sequence, staging = args.sequence, args.staging
    arguments = args.arguments
    input_mode = args.input
    batch = 'ors-input' if input_mode else 'ors-arguments' if arguments else 'ors-staging' if staging else 'ors-sequence' if sequence else 'ors-results'
    number = '0134' if input_mode else '0133' if arguments else '0130' if staging else '0129' if sequence else '0128'
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
    spec = read(TREE/'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == ('0134-ors-input-error-boundaries.patch' if input_mode else '0133-ors-missing-arguments.patch' if arguments else '0130-ors-staging-error-propagation.patch' if staging else '0129-ors-startup-sequence-failure.patch' if sequence else '0128-ors-command-error-propagation.patch')
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    expected = [('current',23,0),('old',23,11),('sequence',9,0),('commands',58,0)] if staging else [('current',9,0),('old',9,4),('command-regression',58,0)] if sequence else [('current',58,0),('old',58,30)]
    if arguments:
        expected = [('current',20,0),('old',20,12),('commands',58,0),('sequence',9,0)]
    if input_mode:
        expected = [('current',28,0),('old',28,16),('commands',58,0),('arguments',20,0),('sequence',9,0)]
    for suffix, count, failures in expected:
        path = ROOT/f'logs/{batch}-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        if not (arguments and suffix == 'old'):
            assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
        if input_mode and suffix in ['current', 'old']:
            bad = {f'{name}-{entry}' for name in ['read-first', 'read-after-command', 'read-partial', 'read-lookahead', 'close-error', 'directory', 'long-line', 'long-after-command'] for entry in ['direct', 'startup']}
            assert all(c['status']==('FAIL' if suffix=='old' and c['case'] in bad else 'PASS') for c in report['cases'])
            if suffix == 'current':
                assert all('ors_input_failure_blocks_success_and_truncated_execution=1' in c['output'] for c in report['cases'])
                assert all('result=1' in c['output'] and 'tail=0 reboots=0' in c['output'] for c in report['cases'] if c['case'] in bad)
                assert all('calls=0' in c['output'] for c in report['cases'] if c['case'].startswith(('long-line-', 'read-lookahead-', 'read-partial-')))
            else:
                cases = {c['case']: c for c in report['cases']}
                assert 'result=0' in cases['read-first-startup']['output'] and 'reboots=1' in cases['read-first-startup']['output']
                assert 'calls=1' in cases['long-line-direct']['output']
        elif (arguments and suffix in ['current', 'old']) or (input_mode and suffix == 'arguments'):
            bad = {f'{command!r}-{entry}' for command in ['backup', 'backup ', 'backup    ', 'set', 'set ', 'set    '] for entry in ['direct', 'startup']}
            assert all(c['status']==('FAIL' if suffix=='old' and c['case'] in bad else 'PASS') for c in report['cases'])
            if suffix != 'old':
                assert all('ors_missing_argument_rejected_without_crash=1' in c['output'] for c in report['cases'])
                assert all('result=1 tail=0 reboots=0' in c['output'] for c in report['cases'] if c['case'] in bad)
            else:
                assert sum('runtime error: null pointer' in c['output'] for c in report['cases']) == 8
                assert sum('result=0 tail=1' in c['output'] for c in report['cases'] if c['case'] in bad) == 4
        elif staging and suffix in ['current','old']:
            failed = {f'{entry}-{fault}' for entry in ['copy','check','action','action-prior'] for fault in ['chmod','unlink','open'] if not(entry=='action-prior' and fault=='open')}
            assert all(c['status']==('FAIL' if suffix=='old' and c['case'] in failed else 'PASS') for c in report['cases'])
            if suffix=='current':
                assert all('ors_staging_source_preserved=1' in c['output'] for c in report['cases'])
                assert all('source=1' in c['output'] for c in report['cases'] if c['case'].endswith(('-chmod','-unlink','-open')))
            else:
                assert any('source=0' in c['output'] for c in report['cases'] if c['status']=='FAIL')
        elif (sequence and suffix!='command-regression') or ((staging or arguments or input_mode) and suffix=='sequence'):
            failed = {'temporary-0-cache-1','temporary-1-cache--1','temporary-1-cache-0','temporary-1-cache-1'}
            assert all(c['status']==('FAIL' if suffix=='old' and c['case'] in failed else 'PASS') for c in report['cases'])
            if suffix in ['current','sequence']:
                assert all('ors_sequence_failure_preserved=1' in c['output'] for c in report['cases'])
            else:
                assert any('result=0 calls=2 tail=1 cache_checks=1 reboots=1' in c['output'] for c in report['cases'] if c['status']=='FAIL')
        elif suffix=='old':
            assert all(c['status']==('FAIL' if '-failure-' in c['case'] else 'PASS') for c in report['cases'])
            assert any('tail=1 reboots=1' in c['output'] for c in report['cases'] if c['status']=='FAIL')
        else:
            assert all('tail=0 reboots=0' in c['output'] for c in report['cases'] if '-failure-' in c['case'])
        reports[suffix] = dict(cases=count,failures=failures,sha256=sha(path))
    before = entries(ROOT/('imgs/built/recovery-dijun-unified-ors-arguments.img' if input_mode else 'imgs/built/recovery-dijun-unified-aux-wipe.img' if arguments else 'imgs/built/recovery-dijun-unified-ors-sequence.img' if staging else 'imgs/built/recovery-dijun-unified-ors-results.img' if sequence else 'imgs/built/recovery-dijun-unified-terminal-shutdown.img'))
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert changed == ['prop.default','ramdisk-files.sha256sum','system/bin/recovery'], changed
    package = read(image.with_suffix('.json'))
    assert package['sha256']==sha(image) and len(package['profiles'])==6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',scope=__doc__,image_sha256=sha(image),production_sources=len(provenance['files']),jobs=provenance['jobs'],reports=reports,changed_ramdisk_entries=changed,
                  limits='Host original complete ORS parser/startup action using private files; manager operations, ExecCmd, settings, console, sleeps and final reboot are fixtures. No physical operations, full GUI/FIFO response status, complete ORS shutdown admission, transactional rollback or full OTA. RTC untouched; existing OTA reused.')
    (ROOT/f'logs/{batch}-delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: patch{number}; {reports}; clean image/six profiles')


if __name__ == '__main__':
    main()
