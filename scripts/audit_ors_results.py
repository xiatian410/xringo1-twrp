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
    modes.add_argument('--reboot', action='store_true')
    modes.add_argument('--cli', action='store_true')
    modes.add_argument('--cli-joined', action='store_true')
    args = parser.parse_args()
    sequence, staging = args.sequence, args.staging
    arguments = args.arguments
    input_mode = args.input
    if args.reboot:
        return audit_reboot()
    if args.cli:
        return audit_cli()
    if args.cli_joined:
        return audit_cli_joined()
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


def audit_reboot():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-ors-reboot.img'
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
    assert patch['file'] == '0135-ors-deferred-reboot.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    for suffix, count, failures in [('current',16,0),('old',16,16),('input',28,0),('commands',58,0),('arguments',20,0),('sequence',9,0),('sideload',23,0)]:
        path = ROOT/f'logs/ors-reboot-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
        if suffix=='current':
            assert all('ors_closed_before_gui_reboot_reservation=1' in c['output'] for c in report['cases'])
        reports[suffix] = dict(cases=count,failures=failures,sha256=sha(path))
    source = (ANDROID/'bootable/recovery/openrecoveryscript.cpp').read_text()
    assert 'TWFunc::TwReboot(' not in source
    startup = (ANDROID/'bootable/recovery/twrp.cpp').read_text()
    assert 'hooks->run_script();\n    // Complete startup' in startup
    assert 'if (OpenRecoveryScript::HasPendingReboot()) return;' in startup
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-ors-input.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert set(changed) == {'prop.default','ramdisk-files.sha256sum','system/bin/recovery'}, changed
    package = read(image.with_suffix('.json'))
    assert package['sha256']==sha(image) and len(package['profiles'])==6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',image_sha256=sha(image),production_sources=len(provenance['files']),jobs=provenance['jobs'],reports=reports,changed_ramdisk_entries=changed,
        limits='Original ORS parser/action/queue and GUI consumer with real executor; private files, final close error injection, DataManager/capability/sync/absent minadbd fixtures. Startup prompt bypass statically checked. No full GUI/USB, descendant/process-wide shutdown, staging concurrency or physical reboot. Historical OTA reused.')
    (ROOT/'logs/ors-reboot-delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: patch0135; ORS16/old16 failures; input28/commands58/arguments20/sequence9/sideload23; clean image/six profiles')


def audit_cli():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-cli-results.img'
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
    assert patch['file'] == '0138-cli-command-result-propagation.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    for suffix, count, failures in [('current',24,0),('old',24,18),('commands',58,0),('reboot',16,0),('input',28,0),('fifo',16,0),('joined',13,0)]:
        path = ROOT/f'logs/cli-results-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        if suffix!='old':
            assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
        if suffix=='current':
            assert all('cli_execution_failure_reaches_listener_completion=1' in c['output'] for c in report['cases'])
        if suffix=='old':
            normal = {'wipe-success','script-success','script-reboot','get-success','decrypt-success','reboot'}
            assert all(c['status']==('PASS' if c['case'] in normal else 'FAIL') for c in report['cases'])
            cases = {c['case']:c for c in report['cases']}
            assert all('runtime error:' in cases[n]['output'] for n in ['empty','spaces'])
            assert 'AddressSanitizer: SEGV' in cases['no-callback']['output']
            assert 'completion=0' in cases['wipe-failure']['output']
        reports[suffix] = dict(cases=count,failures=failures,sha256=sha(path))
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-cli-output.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert changed == ['prop.default','ramdisk-files.sha256sum','system/bin/recovery'], changed
    package = read(image.with_suffix('.json'))
    assert package['sha256']==sha(image) and len(package['profiles'])==6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',image_sha256=sha(image),production_sources=len(provenance['files']),jobs=provenance['jobs'],reports=reports,changed_ramdisk_entries=changed,
        limits='Host original CLI wrapper/parser/action/append/tokenizer/listener twcmd and real executor; private regular files, RLIMIT_FSIZE append failure. Copy/cache discovery/get/decrypt/partition/shell/completion sink are fixtures. Separate real FIFO/client regression retains ORS-body fixture. No same-run complete client/FIFO/ORS/GUI, command exit-status wire protocol, privileged services or physical device proof. Historical OTA reused.')
    (ROOT/'logs/cli-results-delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: patch0138; CLI24/old18 failures; command58/reboot16/input28/FIFO16/join13; clean image/six profiles')


def audit_cli_joined():
    """Check new host-chain evidence against the unchanged production delivery."""
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    provenance = read(image.with_name(image.stem+'-sources.json'))
    assert image.name == 'recovery-dijun-unified-cli-results.img'
    assert sha(image) == index['image_sha256'] == provenance['image_sha256']
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    build = ROOT/provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    path = ROOT/'logs/cli-ors-joined.json'
    report = read(path)
    assert report['status']=='PASS' and len(report['cases'])==10
    expected = {'print','wipe-success','wipe-failure','unknown','script-success','script-failure','decrypt-failure','missing-script','append-failure','long-command'}
    assert {case['case'] for case in report['cases']} == expected
    for name, digest in report['sources'].items():
        assert sha(name) == digest, name
    for case in report['cases']:
        assert case['status']=='PASS' and case['listener_returncode']==0
        assert case['client_returncodes']==[0,0] and case['retry_stdout']=='after\n'
        assert 'original_client_fifo_wrapper_parser_retry=1' in case['output']
        assert 'AddressSanitizer' not in case['output'] and 'runtime error:' not in case['output']
    item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
    assert item['evidence_sha256']==sha(path)
    package = read(image.with_suffix('.json'))
    assert package['sha256']==sha(image) and len(package['profiles'])==6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',image_sha256=sha(image),production_sources=len(provenance['files']),cases=10,report_sha256=sha(path),production_changed=False,new_build=False,scope=report['scope'])
    (ROOT/'logs/cli-ors-joined-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: original CLI/FIFO/wrapper/parser and same-server retry10; unchanged image/sources; no new build')


if __name__ == '__main__':
    main()
