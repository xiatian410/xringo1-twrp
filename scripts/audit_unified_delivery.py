#!/usr/bin/env python3
"""Check delivery/source/evidence consistency; this is not a completion audit.

Does not execute device commands or repeat unchanged functional suites. The
separate image verifier and same-image runtime tests must already have passed.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from sync_device_tree import ANDROID, ROOT, TREE, manifest

REC=ANDROID/'bootable/recovery'

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def check_map(mapping,base=ROOT):
    for name,expected in mapping.items():
        path=Path(name)
        if not path.is_absolute():path=base/path
        assert sha(path)==expected,str(path)

def main():
    report=read(ROOT/'simulation-report.json')
    image=Path(report['image']);image_hash=sha(image)
    assert image_hash==report['image_sha256']
    inspected=read(image.with_suffix('.json'))
    assert inspected['sha256']==image_hash
    provenance=read(image.with_name(image.stem+'-sources.json'))
    assert provenance['image_sha256']==image_hash
    check_map(provenance['files'])
    for path,target in provenance['symlinks'].items():assert os.readlink(path)==target,path
    assert sha(provenance['build_log'])==provenance['build_log_sha256']
    for repo,record in provenance['source_repositories'].items():
        actual=subprocess.check_output(['git','-C',str(ANDROID/repo),'rev-parse','HEAD'],text=True).strip()
        assert actual==record['head'],repo
    assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
    variables=ANDROID/'out/soong/soong.twrp_dijun.variables'
    assert sha(variables)==inspected['status_build_configuration']['soong_variables_sha256']
    context=provenance.get('recording_context',{})
    if context.get('kind')=='post-hoc-source-reconstruction':
        assert context['original_build_time_manifest_available'] is False
        assert 'PASS:' in (ROOT/context['image_reverification_log']).read_text()
        print('PASS:',len(provenance['files']),'current source fingerprints, pinned repositories and verified image agree; manifest reconstructed post hoc, not build-time attestation.')
    else:
        print('PASS:',len(provenance['files']),'source files, pinned repositories, generated tree, build log/configuration and image agree.')

    checks={c['name']:c for c in report['checks']}
    for group in ['checks','additional_checks']:
        for item in report[group]:assert sha(ROOT/item['evidence'])==item['evidence_sha256'],item['name']
    additional={c['name']:c for c in report['additional_checks']}
    triage=read(ROOT/additional['touch-window-log-analysis']['evidence'])
    assert triage['status']=='PASS' and triage['count']==len(triage['cases'])==10
    check_map(triage['sources'])
    cases={c['case']:c['result'] for c in triage['cases']}
    for name in ['reboot-counter','irq-renumbered','capture-error','missing','overlap']:
        assert cases[name]['status']=='insufficient'
    assert cases['coordinates']['touch']['coordinate_event_count']==1
    assert cases['capabilities-only']['touch']['coordinate_event_count']==0
    assert cases['no-irq']['touch']['irqs']['xiaomi_tpsynaptics_tcm']['delta']==0
    cached=read(ROOT/additional['stock-OS4-cached-touch-info-inspection']['evidence'])
    assert cached['status']=='PASS' and cached['count']==len(cached['cases'])==2
    check_map(cached['sources'])
    for case in cached['cases']:
        assert sha(ROOT/case['module'])==case['module_sha256']
        assert sha(ROOT/case['disassembly'])==case['disassembly_sha256']
        assert case['attribute']=='info' and case['mode']=='0444'
    for name,item in report.items():
        if isinstance(item,dict) and 'evidence_sha256' in item:
            assert sha(ROOT/item['evidence'])==item['evidence_sha256'],name
    for name in ['actual-image-profile-activation','binary-policy','init-scripts','USB-helper-binary-policy']:
        result=read(ROOT/checks[name]['evidence'])
        assert result['image_sha256']==image_hash,name
        assert result.get('status',result.get('result'))=='PASS',name
        check_map(result.get('test_sources',{}))
    runtime=read(ROOT/checks['actual-image-profile-activation']['evidence'])
    assert runtime['status']=='PASS' and runtime['tests_run']==9 and runtime['image_sha256']==image_hash
    check_map(runtime['test_sources'])
    check_map(runtime['sources'])
    assert len([c for c in runtime['cases'] if c['phase']=='modules'])>=3
    print('PASS: indexed evidence hashes and actual-image profile/policy/init checks match this artifact.')
    state=read(ROOT/checks['module-initialization-lifecycle']['evidence'])
    assert state['status']=='PASS' and state['image_sha256']==image_hash
    assert state['tests_run']==4 and len(state['cases'])==24 and state['failures']==state['errors']==0
    check_map(state['tests'])
    script=TREE/'profiles/runtime/dijun-runtime.sh'
    assert state['runtime_sha256']==sha(script)
    before=read(ROOT/report['module_state_before_fix']['evidence'])
    assert before['status']=='FAIL' and before['tests_run']==4 and before['failures']==14 and before['errors']==0
    assert len(before['cases'])==24
    check_map(before['tests'])
    old_script=str(ROOT/'backups/module-state-pre-fix/dijun-runtime.sh')
    assert before['runtime_sha256']==sha(old_script)
    assert {k:v for k,v in before['tests'].items() if (Path(k) if Path(k).is_absolute() else ROOT/k)!=Path(old_script)}==state['tests']
    # Keep the original review as history. The current reference review repeats
    # its source/order/interface checks and binds the current paired shell reports.
    reference=report['module_state_reference_review']
    review=read(ROOT/reference['evidence'])
    assert review['status']=='PASS' and review['image_sha256']==image_hash
    check_map(review['sources'])
    assert len(review['static_ordering_checks'])==7 and all(review['static_ordering_checks'].values())
    assert review['executed_show_initstate']['returncode']==0
    assert review['executed_show_initstate']['cases']==3
    assert review['executed_show_initstate']['stdout']=='state=0 output=live\nstate=1 output=coming\nstate=2 output=going\n'
    assert review['current_shell_tests']==dict(tests_run=4,stage_calls=24,failures=0,
        report=checks['module-initialization-lifecycle']['evidence'])
    assert review['original_shell_control']==dict(tests_run=4,stage_calls=24,failures=14,
        report=report['module_state_before_fix']['evidence'])
    kernel_evidence=read(ROOT/'logs/module-initstate-kernel-evidence.json')
    assert {c['sample'] for c in kernel_evidence['cases']}==set(inspected['profiles'])
    assert {c['sample'] for c in review['kernel_interfaces']}==set(inspected['profiles'])
    assert all(c['status']=='PASS' for c in review['kernel_interfaces'])
    assert {c['sample']:c['strings'] for c in review['kernel_interfaces']}=={
        c['sample']:c['strings'] for c in kernel_evidence['cases']}
    for record in kernel_evidence['cases']:
        assert sha(ROOT/'firmware/samples'/record['sample']/'boot.img')==record['boot_sha256']
    print('PASS: same-image module state waits/dependency rejection; same-harness old script fails 14 assertions.')
    plans=read(ROOT/'logs/touch-priority-plans.json')
    assert plans['status']=='PASS' and len(plans['cases'])==6
    check_map(plans['sources']);check_map(plans['tests'])
    assert all(c['touch_closure_last']<c['haptics_closure_first'] for c in plans['cases'])
    print('PASS: six plans finish touch dependencies before haptics-specific dependencies; same-image input registration states pass.')

    bound=['settings-persistence-and-timezone','multiuser-discovery-and-core',
           'multiuser-backend-threads','status-readings','haptics-production-routing',
           'production-LVGL-haptics-and-cancellation','production-archive-restore',
           'production-raw-image-transfer','operation-completion-feedback','restore-session-preflight',
           'backup-session-cancellation','archive-codec-pipeline','MTP-object-lifecycle',
           'MTP-transfer-reconciliation','MTP-event-lifecycle','MTP-native-and-compat-transport',
           'USB-init-configfs-reconciliation','MTP-control-framing','MTP-caller-lifecycle','MTP-storage-receiver','OS4-stable-component-comparison',
           'stock-ARM64-haptics-driver-emulation','stock-ARM64-haptics-lifecycle',
           'haptics-original-DTBO-merge','GUI-haptics-background-owner','GUI-haptics-production-FF-I/O',
           'stock-ARM64-haptics-playback-and-init-boundaries','stock-ARM64-haptics-early-probe',
           'touch-priority-dependency-plans','touch-registration-to-GUI',
           'haptics-runtime-input-registration',
           'stock-ARM64-OS4-touch-startup-and-ISR',
           'stock-ARM64-OS4-touch-configuration-and-probe','OS4-original-touch-DTBO',
           'stock-ARM64-OS4-touch-SPI-and-power',
           'stock-ARM64-OS4-touch-transport-and-selector',
           'stock-ARM64-OS4-touch-panel-setup',
           'stock-ARM64-OS4-touch-wrapper-registration',
           'stock-ARM64-OS4-touch-identification',
           'stock-ARM64-OS4-touch-message-and-ISR',
           'OS4-touch-static-load-order',
           'stock-ARM64-OS4-touch-v2-command-framing',
           'stock-ARM64-OS4-touch-v2-startup-chain',
           'stock-ARM64-OS4-touch-v2-panel-flash-startup',
           'stock-ARM64-OS4-touch-firmware-parser-and-startup',
           'stock-ARM64-OS4-touch-flash-failure-and-background',
           'stock-ARM64-OS4-touch-complete-programming-and-config',
           'stock-ARM64-OS4-touch-IRQ-and-PM-gates',
           'stock-ARM64-OS4-touch-display-suspend-resume',
           'stock-ARM64-OS4-touch-notifier-wrapper-dispatch',
           'stock-ARM64-OS4-touch-original-IC-mode',
           'stock-ARM64-OS4-touch-pending-work-flush',
           'stock-ARM64-OS4-touch-joined-panel-input',
           'stock-ARM64-OS4-haptics-firmware-parser',
           'stock-ARM64-OS4-haptics-firmware-upload',
           'stock-ARM64-OS4-haptics-stock-coefficients',
           'stock-ARM64-OS4-haptics-DSP-config-boundaries',
           'six-sample-Cirrus-haptics-firmware-byte-comparison',
           'stock-ARM64-OS4-haptics-probe-to-stock-upload',
           'stock-ARM64-OS4-haptics-postboost-brownout',
           'stock-ARM64-OS4-haptics-runtime-logger-ASP',
           'stock-ARM64-OS4-haptics-wave-IRQ-input',
           'stock-ARM64-OS4-haptics-probe-selftest',
           'stock-ARM64-OS4-haptics-gain-default',
           'stock-ARM64-OS4-haptics-service-request',
           'stock-ARM64-OS4-haptics-calibration-restore',
           'stock-ARM64-OS4-haptics-calibration-coefficients',
           'haptics-independent-diagnostic',
           'haptics-diagnostic-ARM64-startup',
           'video-frames-encode-decode',
           'stock-ARM64-OS4-haptics-mailbox-IRQ-completion',
           'stock-ARM64-OS4-haptics-active-erase-completion',
           'stock-ARM64-OS4-haptics-regmap-pre-IRQ',
           'stock-ARM64-haptics-PLL-and-chip-identification',
           'stock-ARM64-OS2-OS3-haptics-probe-prefix']
    for name in bound:
        result=read(ROOT/checks[name]['evidence']);assert result['status']=='PASS',name
        for field in ['sources','shared_sources','test_sources','tests','headers','configuration','artwork','emulator_files','libfdt_sources']:
            base=ROOT
            if name=='settings-persistence-and-timezone':base=REC if field=='sources' else ROOT/'tests'
            check_map(result.get(field,{}),base)
        if 'lvgl' in result:
            check_map(result['lvgl']['source_files'])
            for frame in result['rendered_frames']:assert sha(ROOT/frame['path'])==frame['sha256']
        if name in ['stock-ARM64-haptics-driver-emulation','stock-ARM64-haptics-lifecycle','haptics-original-DTBO-merge',
                    'stock-ARM64-haptics-playback-and-init-boundaries','stock-ARM64-haptics-early-probe']:
            expected={'stock-ARM64-haptics-driver-emulation':120,'stock-ARM64-haptics-lifecycle':90,
                      'haptics-original-DTBO-merge':48,'stock-ARM64-haptics-playback-and-init-boundaries':120,
                      'stock-ARM64-haptics-early-probe':54}[name]
            assert len(result['cases']) == expected and all(c['status'] == 'PASS' for c in result['cases'])
        if name in ['stock-ARM64-haptics-driver-emulation','stock-ARM64-haptics-lifecycle',
                    'stock-ARM64-haptics-playback-and-init-boundaries','stock-ARM64-haptics-early-probe']:
            for record in result['drivers'].values(): assert sha(ROOT/record['path']) == record['sha256']
        if name == 'stock-ARM64-haptics-lifecycle':
            samples={case['sample'] for case in result['cases']}
            assert samples==set(inspected['profiles'])
            contracts=[case for case in result['cases'] if case['case']=='input-register-capabilities-callbacks']
            assert len(contracts)==6
            expected_caps=[[21,81],[21,93],[21,90],[21,96]]
            for case in contracts:
                contract=case['contract']
                assert case['status']=='PASS'
                assert contract['name']=='cs40l26_input'
                assert contract['capabilities']==expected_caps
                assert contract['ff_max_effects']==96
                assert contract['rumble_flag_enabled'] is False
                assert set(contract['callbacks'])=={'cs40l26_upload_effect','cs40l26_erase_effect',
                                                     'cs40l26_playback_effect','cs40l26_set_gain'}
                assert all(int(address,16)>0 for address in contract['callbacks'].values())
            print('PASS: six stock input-registration contracts expose the expected FF capabilities and callbacks; this is not an ioctl or motor test.')
        if name == 'GUI-haptics-background-owner':
            assert inspected['gui_haptics_worker_compiled']
            assert len(result['cases']) == 16 and all(c['status']=='PASS' for c in result['cases'])
        if name == 'GUI-haptics-production-FF-I/O':
            assert len(result['cases']) == 4 and all(c['status']=='PASS' for c in result['cases'])
        if name == 'stock-ARM64-OS4-touch-startup-and-ISR':
            assert len(result['cases']) == 88 and all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers']) == {'os4-current','os4-stable'}
            for record in result['drivers'].values(): assert sha(ROOT/record['path']) == record['sha256']
        if name in ['stock-ARM64-OS4-touch-configuration-and-probe','OS4-original-touch-DTBO']:
            expected=62 if name=='stock-ARM64-OS4-touch-configuration-and-probe' else 2
            assert len(result['cases']) == expected and all(c['status']=='PASS' for c in result['cases'])
            for record in result.get('drivers',{}).values(): assert sha(ROOT/record['path']) == record['sha256']
        if name=='stock-ARM64-OS4-touch-SPI-and-power':
            assert len(result['cases'])==58 and all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            assert len(result['emulator_files'])>=70
            for record in result['drivers'].values():assert sha(ROOT/record['path'])==record['sha256']
        if name in ['stock-ARM64-OS4-touch-transport-and-selector','stock-ARM64-OS4-touch-panel-setup']:
            expected=86 if name.endswith('transport-and-selector') else 22
            assert len(result['cases'])==expected and all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            assert len(result['emulator_files'])>=70
            for record in result['drivers'].values():assert sha(ROOT/record['path'])==record['sha256']
            if name.endswith('panel-setup'):
                loops=[c for c in result['cases'] if c['case']=='empty-lockdown']
                assert len(loops)==2 and all(c['flash_reads']>100 for c in loops)
        if name=='stock-ARM64-OS4-touch-wrapper-registration':
            assert len(result['cases'])==50 and all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={s+'-'+kind for s in ['os4-current','os4-stable'] for kind in ['wrapper','synaptics']}
            for record in result['drivers'].values():assert sha(ROOT/record['path'])==record['sha256']
            for c in result['cases']:
                if c['case']=='raw-callback-error-hidden':
                    assert c['result']==2 and c['callbacks']==[{'value':0,'result':-110}]
        if name=='stock-ARM64-OS4-touch-identification':
            assert len(result['cases'])==62 and all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            assert result['synthetic_v2_header']=='10000027'
            assert checks[name]['count']==len(result['cases'])
            for record in result['drivers'].values():assert sha(ROOT/record['path'])==record['sha256']
            for sample in result['drivers']:
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==31
                for key in ['v2-zero-write-size','v2-zero-read-size']:
                    assert subset[key]['result']==subset[key]['max_write']==subset[key]['max_read']==0
                assert subset['v2-size-command-error']['result']==-242
        if name=='stock-ARM64-OS4-touch-message-and-ISR':
            assert checks[name]['count']==len(result['cases'])==90
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            assert len(result['emulator_files'])>=70
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==45
                bad=subset['v1-invalid-marker']
                assert bad['result']==-242 and len(bad['reads'])==len(bad['waits'])==20
                assert subset['v1-fragmented']['output_length']==8
                failed=subset['v2-allocation-report']
                assert failed['result']==failed['report_length']==failed['output_length']==0
                for protocol in [1,2]:
                    replay=subset[f'v{protocol}-ISR-reuse-empty']
                    assert replay['report_length']==0 and replay['isr_output_length']==8
                    assert replay['events']==replay['initial_events'] and replay['events']
                    pending=subset[f'v{protocol}-pending-command-read-error']
                    assert pending['result']==-110 and pending['command_state']==0xffffffff
                    assert len(pending['completed'])==1
        if name=='stock-ARM64-OS4-touch-v2-command-framing':
            assert checks[name]['count']==len(result['cases'])==78
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            assert len(result['emulator_files'])>=70
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==39
                for key in ['header-crc-exhausted','sequence-exhausted']:
                    case=subset[key]
                    assert case['result']==0 and case['report_id']=='fe' and case['output_length']==0
                    assert len(case['reads'])==len(case['writes'])==6
                case=subset['payload-crc-exhausted']
                assert case['result']==0 and case['output']=='00'*8 and len(case['reads'])==8
                assert len(case['writes'])==7 and case['report_id']=='11'
                assert subset['mode-first-write-error']['result']==0
                assert subset['mode-second-write-error']['result']==-110
                assert subset['allocation-report']['result']==0 and subset['allocation-report']['output_length']==0
                case=subset['config-crc-exhausted-ISR']
                assert case['result']==0 and case['config']=='00'*13 and case['config_length']==13
                assert subset['config-timeout-ISR']['result']==-110 and not subset['config-timeout-ISR']['events']
                assert any(e[1:]==[3,53,64400] for e in subset['config-app-ISR']['events'])
        if name=='stock-ARM64-OS4-touch-v2-startup-chain':
            assert checks[name]['count']==len(result['cases'])==44
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            assert len(result['emulator_files'])>=70
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==22
                for key in ['connect-config-timeout','connect-app-timeout-exhausted',
                            'background-mode-only-missing-config','background-update-exhausted']:
                    case=subset[key]
                    assert case['result']==case['config_length']==0
                    assert len(case['inputs'])==len(case['queued'])==len(case['irq_requests'])==1
                    assert case['events']==case['worker_commands']==[] and case['remaining']==0
                recovered=subset['background-config-recovered']
                assert recovered['modes']==[11,1] and recovered['worker_commands']==[32,37]
                assert recovered['config_length']==13 and recovered['firmware_updates']==1
                assert any(e[1:]==[3,53,64400] for e in recovered['events'])
                exhausted=subset['connect-app-timeout-exhausted']
                assert exhausted['connect_commands']==[10,9]+[32,10,10,10]*3+[31]
                assert subset['background-update-exhausted']['firmware_updates']==3
                assert subset['connect-irq-error']['result']==-5 and not subset['connect-irq-error']['queued']
                assert subset['mode-app-stays-bootloader']['result']==-242
                assert subset['mode-app-write-error']['result']==-110
                assert subset['size-command-error']['result']==-245
        if name=='stock-ARM64-OS4-touch-v2-panel-flash-startup':
            assert checks[name]['count']==len(result['cases'])==32
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            assert len(result['emulator_files'])>=70
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==16
                loop=subset['lockdown-empty']
                assert loop['instruction_budget'] and loop['result'] is None
                assert loop['flash_area_calls']==loop['flash_reads']>100
                assert not loop['queued'] and not loop['inputs'] and loop['remaining']==2
                for key,n in [('original-flash',1),('original-flash-read-error-recovered',2)]:
                    c=subset[key]
                    assert c['result']==0 and c['flash_reads']==0 and c['flash_area_calls']==n
                    assert c['mode']=='0201' and c['config_length']==13 and c['remaining']==0
                    cmds=[int(w['packet'][:2],16) for w in c['writes']]
                    assert cmds==[10,9,32,37]+[2,31,16,19,20]*n+[6,5,10]
                    assert any(e[1:]==[3,53,64400] for e in c['events'])
                error=subset['enable-write-error']
                assert error['result']==0 and len(error['inputs'])==1 and error['writes'][5]['result']==-110
                no_report=subset['enable-error-no-report']
                assert no_report['result']==0 and len(no_report['inputs'])==1 and not no_report['events']
                raw=subset['raw-mode-ISR']
                assert raw['raw_frames'] and not raw['events']
                c=subset['config-timeout']
                assert c['result']==c['config_length']==0 and c['mode']=='020b' and not c['events']
                assert [int(w['packet'][:2],16) for w in c['writes']]==[10,9,32,37,31,10]
        if name=='stock-ARM64-OS4-touch-firmware-parser-and-startup':
            assert checks[name]['count']==len(result['cases'])==26
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            assert len(result['emulator_files'])>=70
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==13
                match=subset['match']
                assert match['result']==0 and len(match['crcs'])==3 and not match['writes']
                assert [a['index'] for a in match['comparisons'][0]]==[2,3,5]
                for key in ['build-mismatch','config-mismatch','config-last-mismatch','forced']:
                    c=subset[key]
                    assert c['result']==-5 and c['pending']==c['remaining']==0
                    assert len(c['writes'])==1 and c['writes'][0]['packet'].startswith('02')
                for key in ['bad-magic','bad-BOOT_CONFIG-crc','bad-APP_CODE-crc','bad-APP_CONFIG-crc']:
                    c=subset[key]
                    assert c['result']==-241 and not c['completions'] and not c['writes']
                restored=subset['joined-match-config-restored']
                assert restored['result'] is None and restored['config_length']==13
                assert len(restored['updates'])==1 and len(restored['completions'])==1
                assert any(e[1:]==[3,53,64400] for e in restored['events'])
                c=subset['joined-missing-config-flash-access-fails']
                assert c['result'] is None and len(c['updates'])==3 and len(c['inputs'])==1
                assert c['config_length']==c['remaining']==0 and not c['events'] and c['mode']=='020b'
                c=subset['joined-bad-crc']
                assert len(c['updates'])==3 and len(c['crcs'])==12 and not c['completions']
                assert c['events'] and c['config_length']==13
        if name=='stock-ARM64-OS4-touch-flash-failure-and-background':
            assert checks[name]['count']==len(result['cases'])==32
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==16
                for key,c in subset.items():
                    assert c['pending']==0
                    if key.startswith('joined-'):
                        assert c['result'] is None and len(c['inputs'])==1
                        assert len(c['updates'])==len(c['completions'])==3
                        assert c['commands'].count(17)==c['commands'].count(4)==3
                        assert 18 not in c['commands'] and 32 not in c['commands'] and 37 not in c['commands']
                        assert c['mode']==('0201' if key.endswith('-1') else '020b')
                        missing='missing' in key
                        assert c['config_length']==(0 if missing else 13)
                        assert bool(c['events'])==bool(not missing)
                    else:
                        assert c['result']==-5 and len(c['completions'])==1
                        assert not c['inputs'] and not c['events']
                assert subset['write-first']['commands']==[10,9,2,31,16,17,18,4]
                assert subset['write-second']['commands']==[10,9,2,31,16,17,18,18,4]
                for key in ['zero-block','large-block','zero-page','boot-info-error']:
                    assert subset[key]['commands']==[10,9,2,31,16] and subset[key]['mode']=='020b'
                assert subset['erase-boot']['mode']==subset['erase-reset-error']['mode']=='020b'
                assert subset['erase-app']['mode']=='0201'
        if name=='stock-ARM64-OS4-touch-original-IC-mode':
            assert checks[name]['count']==len(result['cases'])==22
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={s+'-'+k for s in ['os4-current','os4-stable'] for k in ['wrapper','synaptics']}
            for record in result['drivers'].values():assert sha(ROOT/record['path'])==record['sha256']
            for sample in ['os4-current','os4-stable']:
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==11
                for label,c in subset.items():
                    sent=label in ['direct-normal','direct-command-error','notifier-normal','notifier-command-error','notifier-config-error']
                    assert c['commands']==([dict(command=199,payload='310a00',result=-110 if label.endswith('command-error') else 0)] if sent else [])
                    if label.startswith('notifier-'):
                        assert c['result']==(-110 if label=='notifier-config-error' else 0)
                        assert c['wrapper_suspended']==0 and c['active']==1
                        assert c['bridge']==[[0,0],[1,c['result']]] and c['ic_modes']==[[2,0]]
                        assert c['repeated_on_skips_callback']
                        assert bool(c['events'])==(label!='notifier-config-error')
                        assert c['config_length']==(0 if label=='notifier-config-error' else 13)
        if name=='stock-ARM64-OS4-touch-notifier-wrapper-dispatch':
            assert checks[name]['count']==len(result['cases'])==30
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={sample+'-'+kind for sample in ['os4-current','os4-stable'] for kind in ['wrapper','synaptics']}
            for record in result['drivers'].values():assert sha(ROOT/record['path'])==record['sha256']
            for sample in ['os4-current','os4-stable']:
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==15
                normal=subset['ordered-off-on-duplicate-early-off-on']
                assert normal['bridge']==[[0,0],[1,0],[0,0],[1,0]]
                assert len(normal['work_requests'])==len(normal['flushes'])==5
                assert normal['wrapper_suspended']==0 and normal['synaptics_state']==1
                assert normal['config_length']==13 and normal['events']
                for label,code in [('config-error',-110),('power-error',-19),('disabled-dispatch',-1),('missing-callback',None)]:
                    c=subset[label+'-worker-clears-flag'];snap=c['failure_snapshot']
                    assert snap['wrapper_suspended']==snap['config_length']==0 and not snap['events']
                    assert snap['synaptics_state']==int(label=='config-error')
                    assert snap['bridge']==([[0,0]] if code is None else [[0,0],[1,code]])
                    assert c['repeated_on_skips_callback'] is True
                    if label=='config-error':
                        assert c['bridge'][-2:]==[[0,0],[1,0]] and c['config_length']==13 and c['events']
                    else:
                        assert c['bridge']==snap['bridge'] and c['config_length']==0 and not c['events']
                for key in ['ignored-event-0','ignored-event-4','ignored-event-7','ignored-event-8',
                            'invalid-panel','negative-panel','null-notification','unregistered-panel']:
                    assert not subset[key]['bridge'] and not subset[key]['work_requests']
                assert subset['reject-resume']['wrapper_suspended']==1 and subset['reject-resume']['bridge']==[[0,0]]
                for key in ['reject-suspend','reject-resume']:assert subset[key]['work_requests'][-1]['accepted']==0
        if name=='stock-ARM64-OS4-touch-display-suspend-resume':
            assert checks[name]['count']==len(result['cases'])==48
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==24
                roundtrip=subset['two-display-roundtrips']
                assert roundtrip['commands']==[44,32,37]*2 and roundtrip['requested_sleeps_ms']==[100]*2
                assert roundtrip['state']==roundtrip['irq_flag']==1 and roundtrip['config_length']==13
                recovery=subset['config-failure-next-display-cycle-recovers']
                assert recovery['direct_resume_repaired_config'] is False and recovery['next_cycle_repaired_config'] is True
                assert recovery['commands']==[44,32,37]*2 and recovery['config_length']==13 and recovery['events']
                for key,code in [('config-timeout',-110),('config-empty',-22),('app-timeout',-110),
                                 ('bootloader',-22),('read-timeout',-5),('unexpected-reset-report',-5),
                                 ('software-reset-fails',-5),('normal-exhausted',-110),('dynamic-exhausted',-5)]:
                    c=subset[key]
                    assert c['result']==code and c['state']==1 and c['config_length']==0 and not c['events']
                assert subset['app-timeout']['commands']==[44,32,32,32] and subset['app-timeout']['drained_events']==10
                for key in ['report-first-error','report-second-error','report-both-errors']:
                    c=subset[key]
                    assert c['result']==0 and c['reports']==[[0x4010000,192,0],[0x4010000,17,1]]
                    assert c['config_length']==13 and c['events'] and c['second_resume_skips_recovery']
                assert not subset['raw-mode-retained']['reports'] and subset['raw-mode-retained']['events']
                assert subset['power-fails']['result']==-19 and subset['power-fails']['state']==0
                assert subset['power-fails']['irq_flag']==0 and not subset['power-fails']['events']
                assert subset['pinctrl-error-ignored']['result']==0 and subset['pinctrl-error-ignored']['pinctrl_calls']
                assert subset['suspend-pending']['requested_sleeps_ms']==[20]*3
                assert subset['suspend-sleep-error']['result']==-110 and not subset['suspend-sleep-error']['irq_actions']
                assert subset['normal-retry']['sleep_commands']==[45,45]
                assert subset['normal-exhausted']['sleep_commands']==[45]*4
                assert subset['dynamic-exhausted']['dynamics']==['090000']*4
                for key in ['two-display-roundtrips','normal-sensing','normal-retry','pinctrl-error-ignored']:
                    assert [0x4030000,3,53,64400] in subset[key]['events']
        if name=='stock-ARM64-OS4-touch-IRQ-and-PM-gates':
            assert checks[name]['count']==len(result['cases'])==40
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==20
                for depth in [0,1,3]:
                    c=subset['enable-depth-'+str(depth)]
                    assert c['result']==0 and c['irq_flag']==1 and c['irq_depth']==0
                    expected=[['enable_irq',76,n] for n in range(depth,0,-1)] if depth else [['enable_irq',76,0]]
                    assert c['irq_actions']==expected
                stale=subset['enable-stale-flag-skips-depth']
                assert stale['irq_depth']==3 and stale['irq_flag']==1 and not stale['irq_actions']
                zero=subset['zero-IRQ-success-without-enabling']
                assert zero['result']==0 and zero['irq_flag']==0 and not zero['irq_actions']
                stuck=subset['unchanged-depth-budget']
                assert stuck['execution']=='finite budget exhausted as expected'
                assert stuck['irq_depth']==2 and stuck['irq_flag']==0 and len(stuck['irq_actions'])>100
                assert all(a==['enable_irq',76,2] for a in stuck['irq_actions'])
                for clear_after,count in [('None',150),('1',1),('3',3)]:
                    c=subset['disable-pending-'+clear_after]
                    assert c['requested_sleeps_ms']==[20]*count
                    assert c['irq_actions']==[['disable_irq_nosync',76,0]]
                    assert c['wake_requests']==[[76,0]] and c['irq_flag']==c['wake_flag']==0
                failed=subset['wake-enable-result--5']
                assert failed['wake_result']==-5 and failed['wake_flag']==failed['irq_flag']==1
                pm=subset['PM-roundtrip-only-flags-and-completion']
                assert pm['result']==pm['pm_flag']==0 and pm['completions']==[0x40006d0]
                assert not pm['irq_actions'] and not pm['wake_requests']
                for sensorhub in [0,1]:
                    c=subset['ISR-PM-flag-sensorhub-'+str(sensorhub)]
                    assert c['pm_flag']==1 and c['result']==1
                    assert [0x4030000,3,53,64400] in c['events'] and [0x4030000,3,54,158900] in c['events']
        if name=='stock-ARM64-OS4-touch-complete-programming-and-config':
            assert checks[name]['count']==len(result['cases'])==26
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==13
                full=subset['full']['checked_chunks']
                assert len(full)==627 and subset['full']['programming_writes']==625
                assert subset['full']['erase_commands']==2 and subset['full']['result']==0
                assert subset['config-only']['programming_writes']==25 and subset['config-only']['erase_commands']==1
                for key,c in subset.items():
                    assert c['pending']==0
                    assert len(c['checked_chunks'])==c['programming_writes']+c['erase_commands']
                    if key.startswith('joined-'):
                        repeats=2 if key=='joined-retry-after-config-last-error' else 1
                        assert c['result'] is None and len(c['inputs'])==1
                        assert len(c['updates'])==len(c['completions'])==repeats
                        assert c['checked_chunks']==full*repeats
                        missing=key in ['joined-reset-bootloader','joined-config-timeout','joined-config-empty']
                        assert c['config_length']==(0 if missing else 13)
                        assert bool(c['events'])==bool(not missing)
                        assert c['mode']==('020b' if key=='joined-reset-bootloader' else '0201')
                        assert c['commands'].count(32)==c['commands'].count(37)==int(key!='joined-reset-bootloader')
                    else:
                        assert len(c['completions'])==1
                assert subset['reset-bootloader']['result']==0 and subset['reset-bootloader']['mode']=='020b'
                assert subset['reset-bootloader']['checked_chunks']==full
                for key in ['reset-timeout','reset-rejects-status','config-last-write-error']:
                    assert subset[key]['result']==-5 and subset[key]['checked_chunks']==full
                assert subset['app-last-write-error']['programming_writes']==600
                assert subset['config-erase-error']['programming_writes']==600
        if name=='stock-ARM64-OS4-haptics-firmware-parser':
            assert checks[name]['count']==len(result['cases'])==64
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                for firmware in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
                    subset={c['case']:c for c in result['cases'] if c['sample']==sample and c['firmware']==firmware}
                    assert len(subset)==16
                    inventory=result['inventories'][sample+'/'+firmware]
                    expected_count=525 if firmware=='cs40l26.wmfw' else 428
                    assert inventory['coefficients']==expected_count
                    c=subset['write-read-error']
                    assert c['result']==-5 and c['coefficients']==expected_count
                    assert c['raw_writes']==inventory['writes'] and len(c['reads'])==1
                    c=subset['parse-only-read-error']
                    assert c['result']==-5 and not c['raw_writes'] and c['coefficients']==expected_count
                    for key,lookup in [('zero-algorithm-table',-22),('resolved-algorithm-table',0)]:
                        c=subset[key]
                        assert c['result']==0 and c['lookup_result']==lookup and len(c['reads'])==8
                    for key in ['raw-first-error','raw-middle-error','raw-last-error']:
                        c=subset[key]
                        assert c['result']==-5 and not c['reads']
                        assert c['raw_writes']==inventory['writes'][:len(c['raw_writes'])]
                    for key in ['bad-magic','bad-header-size','bad-format','bad-core','bad-version','unaligned-size']:
                        c=subset[key]
                        assert c['result']==-22 and not c['reads'] and not c['raw_writes'] and c['coefficients']==0
        if name=='stock-ARM64-OS4-haptics-firmware-upload':
            assert checks[name]['count']==len(result['cases'])==72
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                for firmware in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
                    subset={c['case']:c for c in result['cases'] if c['sample']==sample and c['firmware']==firmware}
                    assert len(subset)==12
                    assert subset['request-missing']['result']==-2 and not subset['request-missing']['raw_writes']
                    for key in ['pre-mailbox-error','pre-PM-stuck','pre-shutdown-wrong','pre-state-stuck','pre-core-write-error']:
                        assert subset[key]['result'] in [-5,-22,-110] and not subset[key]['raw_writes']
                    assert subset['pre-PM-stuck']['result']==-110 and len(subset['pre-PM-stuck']['sleeps'])==5
                    assert subset['pre-state-stuck']['result']==-22 and len(subset['pre-state-stuck']['sleeps'])==10
                    assert subset['bad-firmware-magic']['result']==-22 and not subset['bad-firmware-magic']['raw_writes']
                    for key in ['raw-first-error','algorithm-count-read-error','unknown-firmware-ID','old-firmware-revision','config-MEM_RDY-error']:
                        assert subset[key]['raw_writes']
                    c=subset['config-MEM_RDY-error']
                    assert c['result']==-5 and c['entries'].count('cl_dsp_firmware_parse')==1
                    assert 'cs40l26_dsp_config' in c['entries'] and len(c['requests'])>=5
                ident=[c for c in result['cases'] if c['sample']==sample and c['firmware']=='identity-only']
                assert len(ident)==12 and all(c['status']=='PASS' for c in ident)
        if name=='stock-ARM64-OS4-haptics-stock-coefficients':
            assert checks[name]['count']==len(result['cases'])==16
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                for firmware in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
                    subset={c['case']:c for c in result['cases'] if c['sample']==sample and c['firmware']==firmware}
                    assert len(subset)==4
                    stock=subset['stock-tables-and-bins']
                    assert len(stock['algorithm_rows'])==14
                    assert len(stock['parameter_writes'])==(34 if firmware=='cs40l26.wmfw' else 28)
                    assert stock['messages']==['Failed to set MEM_RDY to initialize RAM\n']
                    for c in subset.values():
                        assert c['result']==-5 and c['fw_loaded']==0
                        assert c['updates']==[dict(address=0x2900,mask=2,value=2)]
                        assert c['entries'][-1]=='cs40l26_dsp_config'
                    assert len(subset['main-bin-missing']['parameter_writes'])<len(stock['parameter_writes'])
                    assert len(subset['main-bin-invalid-revision']['parameter_writes'])<len(stock['parameter_writes'])
                    assert len(subset['coefficient-first-write-error']['parameter_writes'])<len(stock['parameter_writes'])
        if name=='stock-ARM64-OS4-haptics-DSP-config-boundaries':
            assert checks[name]['count']==len(result['cases'])==36
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            check_map(result['sources']);check_map(result['tests'])
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                for firmware in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
                    subset={c['case']:c for c in result['cases'] if c['sample']==sample and c['firmware']==firmware}
                    assert len(subset)==9
                    c=subset['call-ram-write-exhausted']
                    assert c['result']==-62 and c['fw_loaded']==0 and len(c['sleeps'])==20
                    assert len([w for w in c['writes'] if w['address']==0x2800ff8])==20
                    assert not c['raw_reads'] and not c['bulk_writes'] and not c['debugfs']
                    for key,c in subset.items():
                        assert c['updates'][0]==dict(address=0x2900,mask=2,value=2)
                        if key=='call-ram-write-exhausted':continue
                        assert c['fw_loaded']==1 and len(c['debugfs'])==1
                        assert c['result']==(-22 if key=='HALO-invalid-state' else -5)
                        assert [r['length'] for r in c['raw_reads']]==([132] if key=='active-sequence-read-error' else [132,516])
                        assert all(r['fixture']=='all-FF-immediate-terminator' for r in c['raw_reads'])
                    assert len(subset['first-sequence-write-error']['bulk_writes'])==1
                    assert len(subset['second-sequence-write-error']['bulk_writes'])==2
                    c=subset['GPIO-read-error']
                    assert len(c['bulk_writes'])==5 and 'cs40l26_gpio_config' in c['entries']
                    assert 'cs40l26_irq_update_mask' in subset['IRQ-mask-read-error']['entries']
        if name=='six-sample-Cirrus-haptics-firmware-byte-comparison':
            assert len(result['samples'])==6 and len(result['cross_version'])==7
            assert result['hardware_result']=='unverified'
            check_map(result['sources']);check_map(result['tests'])
            verify=read(ROOT/'logs/haptics-firmware-cross-version-audit-verification.json')
            assert verify['status']=='PASS' and verify['sample_count']==6
            assert verify['firmware_count']==7 and verify['cross_version_identical_count']==7
        if name=='stock-ARM64-OS4-touch-joined-panel-input':
            assert checks[name]['count']==len(result['cases'])==16
            for record in result['drivers'].values():assert sha(ROOT/record['path'])==record['sha256']
            for sample in ['os4-current','os4-stable']:
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==8
                for label,c in subset.items():
                    failed=label in ['input-allocation-error','input-registration-error']
                    assert c['status']=='PASS' and c['connect_result']==0
                    assert [r['name'] for r in c['registration_calls']]==['register_touch_panel','register_xiaomi_input_dev']
                    assert c['registration_calls'][0]['result']==(-1 if label=='panel-workqueue-error' else 0)
                    assert c['registration_calls'][1]['result']==(0 if failed else 0x4030000)
                    assert c['input_pointer']==(0 if failed else 0x4030000)
                    assert c['input_allocations']==1 and c['input_registrations']==int(label!='input-allocation-error')
                    assert c['input_frees']==([0x4030000] if label=='input-registration-error' else [])
                    assert c['worker_returned']==(not failed) and bool(c['invalid_accesses'])==failed
                    if failed:
                        fault,=c['invalid_accesses']
                        assert fault['address']==0x2c0 and fault['size']==8 and fault['value']==0x4000000 and fault['x0']==0
                        assert c['input_private_context'] is None and not c['events']
                    else:
                        assert c['input_private_context']==0x4000000
                        assert c['slots']==[[0x4030000,10,2]]
                    assert c['delivered']==(not failed and label!='config-timeout')
                    assert c['config_length']==(0 if label=='config-timeout' else 13)
                    assert c['requests']==['synaptics_spi_dijun.img'] and c['remaining_report_responses']==0
        if name=='stock-ARM64-OS4-touch-pending-work-flush':
            assert checks[name]['count']==len(result['cases'])==16
            assert set(result['drivers'])=={s+'-'+k for s in ['os4-current','os4-stable'] for k in ['wrapper','synaptics']}
            for record in result['drivers'].values():assert sha(ROOT/record['path'])==record['sha256']
            for sample in ['os4-current','os4-stable']:
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==8
                for label,c in subset.items():
                    assert c['status']=='PASS' and len(c['flushed_workers'])==len(c['events'])-1
                    assert c['config_length']==(13 if c['delivered'] else 0)
                    assert c['wrapper_suspended']==int(label in ['duplicate-off','pending-off-reject-on'])
                    assert c['active']==1-c['wrapper_suspended']
                    flushes=[t for t in c['timeline'] if t['boundary']=='flush']
                    assert len(flushes)==len(c['events'])
                    assert [len(t['pending']) for t in flushes]==[0]+[1]*(len(flushes)-1)
                    if 'reject' in label:
                        assert not c['before_drain']['pending'] and c['work_requests'][-1]['accepted']==0
                c=subset['failed-resume-duplicate-on']
                assert c['bridge']==[[0,0],[1,-110]] and not c['delivered'] and c['config_length']==0
                assert c['before_drain']['config_length']==0
                c=subset['failed-resume-new-cycle']
                assert c['bridge']==[[0,0],[1,-110],[0,0],[1,0]] and c['delivered']
                assert subset['off-on-off-on']['bridge']==[[0,0],[1,0],[0,0],[1,0]]
        if name=='stock-ARM64-OS4-haptics-regmap-pre-IRQ':
            assert checks[name]['count']==len(result['cases'])==12
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==6
                for label,c in subset.items():
                    assert c['status']=='PASS'
                    assert c['chip']['post']==0 and c['chip']['context']==0x4000000 and c['chip']['children']==27
                    assert c['pre_result']==(-5 if label in ['status-read-error','PM-resume-error','pre-error-selected-child'] else 0)
                    if label=='PM-resume-error':
                        assert not c['pre_reads']
                        assert [s['name'] for s in c['pre_PM']]==['__pm_runtime_resume','__pm_runtime_set_status','__pm_runtime_suspend']
                    else:
                        status_read,=c['pre_reads'];assert status_read['address']==0x10004
                        assert status_read['result']==(-5 if label in ['status-read-error','pre-error-selected-child'] else 0)
                        assert [s['name'] for s in c['pre_PM']]==['__pm_runtime_resume','__pm_runtime_suspend']
                    if label.endswith('selected-child'):
                        assert c['child_result']==1 and c['completions']==[['complete_all',0x4000228]]
                        assert c['state']==c['event_count']==0 and len(c['ack_writes'])==1
                    else:assert c['child_result'] is None and not c['completions']
        if name=='stock-ARM64-OS4-haptics-active-erase-completion':
            assert checks[name]['count']==len(result['cases'])==30
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            effect=bytes.fromhex(result['production_effect'])
            assert len(effect)==48 and int.from_bytes(effect[2:4],'little')==7
            assert int.from_bytes(effect[10:12],'little')==80
            assert [int.from_bytes(effect[i:i+2],'little') for i in [16,18,20]]==[0x5a,8,64]
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==15
                for label,c in subset.items():
                    assert c['status']=='PASS' and c['probe_start_gate']=='01'
                    success=label in ['no-start-IRQ','done-before-erase','done-during-wait','start-command-error','two-completions','software-state-done','completed-then-missing']
                    assert c['erase_result']==(0 if success else -62)
                    assert c['before_start_IRQ']==dict(count=int(label.startswith('software-state-')),state=int(label.startswith('software-state-')))
                    assert c['mailbox'][0]==dict(command=0x1800081,result=-5 if label=='start-command-error' else 0)
                    assert c['timeout_requests']==([] if label in ['no-start-IRQ','done-before-erase','start-command-error'] else [580,580] if label=='completed-then-missing' else [10000] if label=='zero-duration-timeout' else [580])
                    for wait in c['waits']:
                        assert wait['pointer']==0x4000228 and wait['before']==dict(counter=0,state=1,count=1)
                        assert wait['result']==int(wait['after']['counter']>0)
                    if c['retry'] is None:
                        assert c['effect_list_empty']==success and len(c['freed_effects'])==int(success)
                        assert c['state']==c['event_count']==int(not success)
                    assert all(r==1 for r in c['irq_results'])
                assert subset['stop-completion-only']['stop_counter']==1 and subset['stop-completion-only']['completion_counter']==0
                c=subset['late-done-retry-erase']
                assert c['erase_result']==-62 and c['retry']==dict(result=0,waits=1,freed=1,counter=0xffffffff)
                assert c['effect_list_empty'] and c['state']==0
                c=subset['completed-then-missing']
                assert c['erase_result']==0 and c['retry']==dict(result=-62,waits=2,freed=1,counter=0)
                assert not c['effect_list_empty'] and c['state']==1
        if name=='stock-ARM64-OS4-haptics-mailbox-IRQ-completion':
            assert checks[name]['count']==len(result['cases'])==30
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==15
                for label,c in subset.items():
                    assert c['status']=='PASS' and c['result']==1 and len(c['raw_writes'])==68
                    assert c['lock_ops'][0][0]=='mutex_lock' and c['lock_ops'][-1][0]=='mutex_unlock'
                    assert {r['name']:r['register'] for r in c['wave_coefficients']}=={'QUEUE_BASE':0x28073fc,'QUEUE_LEN':0x2807400,'QUEUE_WT':0x2807404,'QUEUE_RD':0x2807408}
                    assert len(c['ack_writes'])==(0 if label in ['empty','bulk-read-error','pending-command','message-read-error'] else 2 if label=='start-done-wrap' else 1)
                    count=2 if label=='gpio-trigger' else int(label in ['start-accepted','state-lock-missing','stop-completion'])
                    assert c['event_count']==count and c['vibe_state']==int(count>0)
                    assert c['completions']==([['complete_all',0x4000228]] if label in ['done','done-saturates','start-done-wrap','state-lock-missing'] else [['complete',0x4000208]] if label=='stop-completion' else [])
                    assert len(c['notifications'])==(2 if label=='start-done-wrap' else int(label in ['done','done-saturates','gpio-trigger','gpio-complete','start-accepted']))
                assert [a['value'] for a in subset['start-done-wrap']['ack_writes']]==[0x2807500,0x2807504]
                c=subset['ACK-write-error']
                assert c['ack_writes'][0]['result']==-5 and c['ring'][3]==0x2807500
        if name=='haptics-diagnostic-ARM64-startup':
            assert checks[name]['count']==len(result['cases'])==18
            subset={c['case']:c for c in result['cases']}
            for label,c in subset.items():
                assert c['status']=='PASS' and 'BEGIN upload' not in c['stdout'] and 'BEGIN play' not in c['stdout']
                assert c['result']==(1 if label=='missing-inspect' or label.startswith('regular-file') else 2)
            assert 'errno=2 ' in subset['missing-inspect']['stdout']
            for label in [k for k in subset if k.startswith('regular-file')]:
                assert 'END name result=-1 errno=25 ' in subset[label]['stdout']
                assert 'END close result=0 errno=0 ' in subset[label]['stdout']
        if name=='video-frames-encode-decode':
            assert checks[name]['count']==len(result['cases'])==18
            shapes={(96,64,fps) for fps in [15,24,30,45,60]}|{(97,65,30)}
            assert {(c['mode'],c['width'],c['height'],c['fps']) for c in result['cases']}=={
                (mode,*shape) for mode in ['sequential','queue-drain','queue-resume'] for shape in shapes}
            for c in result['cases']:
                assert c['status']=='PASS' and c['returncode']==0
                count={'sequential':12,'queue-drain':3,'queue-resume':4}[c['mode']]
                assert f'decoded_frames={count} duration_ns=1500000000' in c['stdout']
                assert 'center_YUV_checked=1' in c['stdout']
                assert sha(ROOT/c['artifact'])==c['sha256']
        if name=='haptics-independent-diagnostic':
            assert checks[name]['count']==len(result['cases'])==47
            assert all(c['status']=='PASS' for c in result['cases'])
            subset={c['case']:c for c in result['cases']}
            assert subset['success']['result']==subset['inspect']['result']==0
            assert 'BEGIN upload' not in subset['inspect']['stdout']
            for label in ['sine-gain-success','custom-success','custom-no-gain']:
                assert subset[label]['result']==0
                operations=[l.split()[1] for l in subset[label]['stdout'].splitlines() if l.startswith('BEGIN ')]
                assert operations==['open','name','capabilities']+(['gain'] if label.startswith('sine-') else [])+['upload','play','erase','close']
            for label in ['open-error','name-error','caps-error','wrong-device','unsupported',
                          'upload-error','invalid-id','play-short','play-error','erase-error','close-error']:
                assert subset[label]['result']==1
            build=read(ROOT/'tools/haptics-diagnostic/haptics-diagnostic-arm64.json')
            assert sha(ROOT/build['binary'])==build['sha256']
            check_map(build['inputs'])
            binary=(ROOT/build['binary']).read_bytes()
            assert binary[:6]==b'\x7fELF\x02\x01' and int.from_bytes(binary[18:20],'little')==183
            phoff=int.from_bytes(binary[32:40],'little')
            phsize=int.from_bytes(binary[54:56],'little');phcount=int.from_bytes(binary[56:58],'little')
            assert phsize==56 and phoff+phsize*phcount<=len(binary)
            assert all(int.from_bytes(binary[phoff+i*phsize:phoff+i*phsize+4],'little')!=3 for i in range(phcount))
        if name=='stock-ARM64-OS4-haptics-calibration-coefficients':
            assert checks[name]['count']==len(result['cases'])==36
            assert set(result['defaults'])=={'os4-current','os4-stable'}
            for sample,defaults in result['defaults'].items():
                expected={'f0':('F0_OTP_STORED',0x2802128),
                          'redc':('REDC_OTP_STORED',0x280212c),'q':('Q_STORED',0x2802150)}
                for coefficient_name,address in expected.values():
                    c=defaults[coefficient_name]
                    assert c['coefficient']['register']==address and c['coefficient']['algorithm']==0x400bd
                    assert not c['history'] and c['initial_value'] is None and not c['file_initialization_found']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==18
                for label in ['DT-default-B2','DT-default-write-error','no-DT-default-B2']:
                    c=subset[label]
                    assert c['status']=='PASS' and c['dt_f0']==130<<14 and not c['pm']
                    error=-5 if label=='DT-default-write-error' else 0
                    assert c['result']==error
                    assert c['stores']==([] if label=='no-DT-default-B2' else [dict(address=0x2802128,value=130<<14,result=error)])
                for key,(coefficient_name,address) in expected.items():
                    for label in ['valid-B2','valid-A1','invalid-text','PM-error','write-error']:
                        c=subset[key+'-'+label]
                        rejected=key=='q' and label!='valid-A1'
                        assert c['status']=='PASS'
                        if rejected:
                            assert c['result']==-1 and not c['stores'] and not c['pm']
                        elif label=='invalid-text':
                            assert c['result']==-22 and not c['stores'] and not c['pm']
                        elif label=='PM-error':
                            assert c['result']==-5 and not c['stores'] and len(c['pm'])==1
                        else:
                            assert len(c['stores'])==1 and c['stores'][0]['address']==address and len(c['pm'])==2
                            assert c['stores'][0]['result']==(-5 if label=='write-error' else 0)
                            assert c['result']==-5 if label=='write-error' else c['result']>0
        if name=='stock-ARM64-OS4-haptics-calibration-restore':
            assert checks[name]['count']==len(result['cases'])==16
            assert {c['sample'] for c in result['cases']}=={'os4-current','os4-stable'}
            for sample in ['os4-current','os4-stable']:
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==8
                for label,c in subset.items():
                    assert c['status']=='PASS' and c['readiness_flag']=='00'
                    expected=['redc_stored','f0_stored','q_stored']
                    if label in ['missing-all','sys-path-absent']:expected=[]
                    if label in ['missing-f0','invalid-f0']:expected.remove('f0_stored')
                    if label=='nonpositive-z-q':expected=['f0_stored']
                    assert [Path(w['path']).name for w in c['writes']]==expected
                assert not subset['sys-path-absent']['reads']
                for label in ['valid-input4','valid-input9','sysfs-write-failure']:
                    c=subset[label]
                    assert [w['value'] for w in c['writes']]==['28000','208000','a000']
                    number=9 if label=='valid-input9' else 4
                    assert all(f'/input/input{number}/calibration/' in w['path'] for w in c['writes'])
                    assert all(w['result']==-1 for w in c['writes']) if label=='sysfs-write-failure' else all(w['result']>0 for w in c['writes'])
        if name=='stock-ARM64-OS4-haptics-service-request':
            assert checks[name]['count']==len(result['cases'])==18
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==9
                for duration in [80,300,10000]:
                    c=subset['service-request-'+str(duration)]
                    assert c['status']=='PASS' and c['long_vib_id']==31
                    assert [o['call'] for o in c['operations']]==['write','upload','write']
                    assert c['operations'][1]['custom']=='00001f00'
                    assert c['stop_operations']==[dict(call='erase',effect_id=7)]
                    for count in [5,32]:
                        c=subset[f'custom-{duration}-RAM-count-{count}']
                        assert c['status']=='PASS' and c['ram_count_fixture']==count
                        assert c['upload_status']==(0xffffffea if count==5 else 0)
                        assert c['mailbox']==([] if count==5 else [0x100001f])
                        assert [r['value'] for r in c['registers']]==([] if count==5 else [0,0])
        if name=='stock-ARM64-OS4-haptics-gain-default':
            assert checks[name]['count']==len(result['cases'])==12
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==6
                initial=subset['probe-and-firmware-default']
                assert initial['initial_gain']==[100,100]
                assert not initial['probe_selftest_gain_callback_called']
                assert initial['firmware_default_history'][-1]['value']==0
                assert initial['coefficient']['register']==0x28059e8
                for gain,value in [(0,400),(50,24),(100,0),(101,None),(65535,None)]:
                    c=subset['gain-'+str(gain)]
                    assert c['status']=='PASS'
                    assert c['stored_gain']==(100 if value is None else gain)
                    assert c['queued']==([] if value is None else [0x4000100])
                    assert c['writes']==([] if value is None else [dict(address=0x28059e8,value=value)])
        if name=='stock-ARM64-OS4-haptics-probe-selftest':
            assert checks[name]['count']==len(result['cases'])==16
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==8
                for label,c in subset.items():
                    assert c['status']=='PASS' and len(c['workqueue_spec'])==1
                    assert c['workqueue_spec'][0]['flags']==0x20012 and c['workqueue_spec'][0]['max_active']==1
                    if label=='reject-reverse-queue-model':
                        assert c['model_rejected'];continue
                    assert c['result']==0 and c['fw_loaded']==c['input_registered_flag']==1 and not c['remove_calls']
                    assert len(c['raw_writes'])==68 and not c['pending']
                    assert c['workers']==['cs40l26_upload_worker','cs40l26_vibe_start_worker','cs40l26_erase_worker']
                    assert c['work_requests']==[0x4000120,0x40000c0,0x4000140]
                    assert c['upload_status']==(0xfffffffb if label=='upload-parameter-write-error' else 0)
                    assert c['erase_status']==(0xffffffc3 if label in ['upload-PM-error','upload-parameter-write-error'] else 0)
                    assert c['effect_list_empty']==(label!='erase-PM-error')
                    if label in ['start-before-erase','erase-PM-error','start-mailbox-error']:
                        assert c['selftest_mailbox']==[dict(command=0x1800081,result=-5 if label=='start-mailbox-error' else 0)]
                    else:assert not c['selftest_mailbox']
                    if label=='start-duration-write-error':assert c['selftest_writes'][-1]==dict(worker='cs40l26_vibe_start_worker',address=0x2802134,value=100,result=-5)
                    if label=='upload-parameter-write-error':assert c['selftest_writes']==[dict(worker='cs40l26_upload_worker',address=0x280701c,value=25,result=-5)]
                    if label=='start-PM-error':assert all(w['worker']=='cs40l26_upload_worker' for w in c['selftest_writes'])
        if name=='stock-ARM64-OS4-haptics-wave-IRQ-input':
            assert checks[name]['count']==len(result['cases'])==26
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==13
                for label,c in subset.items():
                    assert c['status']=='PASS' and c['fw_loaded']==1 and c['remove_calls']==[0x4000000]
                    assert c['result']==(-12 if label in ['input-allocation-error','input-FF-error'] else -5)
                    assert len(c['raw_writes'])==68 and len(c['bulk_writes'])==25
                    assert c['mailbox'][-1]==0x03000009 and c['pm_services'][-1]['name']=='__pm_runtime_suspend'
                    assert {r['name']:r['register'] for r in c['wave_coefficients']}=={'NUM_OF_WAVES':0x2802140,'OWT_NUM_OF_WAVES_XM':0x2805368}
                    early=label in ['B2-mailbox-error','playback-config-write-error']
                    assert bool(c['irq_services'])==(not early)
                    if early:assert 'cs40l26_request_irq' not in c['entries']
                    input_case=label.startswith('input-') or label=='MFD-error'
                    assert ('cs40l26_input_init' in c['entries'])==input_case
                    assert c['input_allocations']==([0x4060000] if input_case else [])
                    if input_case:
                        assert len([x for x in c['irq_services'] if x['name']=='devm_request_threaded_irq'])==27
                        assert c['input_services'][-1]['result']==(-12 if label=='input-FF-error' else 0 if label=='input-allocation-error' else -5)
                    assert c['input_registered_flag']==int(label=='MFD-error')
                    if input_case and label!='input-allocation-error':assert c['capabilities']==[[21,81],[21,93],[21,90],[21,96]]
                    failed=[r for r in c['reads'] if r['result']]
                    if label.startswith(('RAM-','OWT-')):
                        target=0x2802140 if label.startswith('RAM-') else 0x2805368
                        assert len(failed)==40 and all(r['address']==target and r['result']==-5 for r in failed)
                        assert c['entries'].count('cs40l26_num_ram_waves')==2
                    else:assert not failed
        if name=='stock-ARM64-OS4-haptics-runtime-logger-ASP':
            assert checks[name]['count']==len(result['cases'])==16
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==8
                for label,c in subset.items():
                    assert c['result']==(-12 if label.endswith('allocation') else -5)
                    assert c['fw_loaded']==1 and c['remove_calls']==[0x4000000] and len(c['raw_writes'])==68
                    assert 'cs40l26_input_init' not in c['entries']
                    pm=c['pm_services']
                    assert [s['name'] for s in pm[:3]]==['__pm_runtime_use_autosuspend','pm_runtime_set_autosuspend_delay','pm_runtime_enable']
                    assert pm[1]['args'][:2]==[0x4060000,2000]
                    if label=='runtime-resume-error':
                        assert 'cs40l26_logger_setup' not in c['entries'] and 'cs40l26_pm_exit' in c['entries']
                        assert [s['name'] for s in pm[-2:]]==['__pm_runtime_set_status','__pm_runtime_suspend']
                        assert pm[-2]['args'][:2]==[0x4060000,0]
                    else:
                        assert 'cs40l26_logger_setup' in c['entries'] and 'cs40l26_pm_exit' in c['entries']
                        assert pm[-1]['name']=='__pm_runtime_suspend'
                    assert {r['name']:r['register'] for r in c['logger_coefficients']}=={'COUNT':0x2805a34,'SOURCE':0x2805a44}
                    if label.startswith('ASP-'):
                        assert 'cs40l26_asp_config' in c['entries'] and c['logger_count']==1
                    if c['multi_writes']:
                        assert c['multi_writes'][0]['values']==[[0x4c40,8,0],[0x4c50,9,0]]
                assert len(subset['ASP-first-sequence']['bulk_writes'])==24
                assert len(subset['ASP-second-sequence']['bulk_writes'])==25
                assert subset['ASP-multi-write']['multi_writes'][0]['result']==-5
        if name=='stock-ARM64-OS4-haptics-postboost-brownout':
            assert checks[name]['count']==len(result['cases'])==26
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==13
                for c in subset.values():
                    assert c['result']==-5 and c['fw_loaded']==1 and c['remove_calls']==[0x4000000]
                    assert len(c['raw_writes'])==68
                    assert 'cs40l26_input_init' not in c['entries'] and 'cs40l26_dc_wd_config' not in c['entries']
                    destinations={p['property']:p['destination'] for p in c['property_destinations']}
                    assert destinations['cirrus,vbbr-thld-uv']==0x1b74 and destinations['cirrus,vpbr-thld-uv']==0x1b90
                    if c['injected_read'] is not None:
                        assert c['register_reads'][-1]==dict(address=c['injected_read'],value=None,result=-5)
                    if c['injected_bulk'] is not None:
                        assert len(c['bulk_writes'])==c['injected_bulk'] and c['bulk_writes'][-1]['result']==-5
                deep=subset['brownout-IRQ-read']
                assert deep['attempted_brownout']=={'0x201c':0x3000,'0x6408':0xa549140c,'0x6404':0x5a491909}
                assert deep['expected_brownout']=={'0x6408':0xa549140c,'0x6404':0x5a491909}
                assert len(deep['bulk_writes'])==22 and deep['injected_read']==0x10114
                for key,count in [('VPBR-high-sequence',19),('VPBR-low-sequence',20),
                                  ('VBBR-high-sequence',21),('VBBR-low-sequence',22)]:
                    assert subset[key]['injected_bulk']==count
        if name=='stock-ARM64-OS4-haptics-probe-to-stock-upload':
            assert checks[name]['count']==len(result['cases'])==16
            assert all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])=={'os4-current','os4-stable'}
            for sample,record in result['drivers'].items():
                assert sha(ROOT/record['path'])==record['sha256']
                subset={c['case']:c for c in result['cases'] if c['sample']==sample}
                assert len(subset)==8
                for key,c in subset.items():
                    assert c['entries'][0]=='cs40l26_probe'
                    assert c['entries'].count('cs40l26_fw_upload')==1
                    assert 'cs40l26_input_init' not in c['entries'] and len(c['remove_calls'])==1
                    assert c['result']==(-2 if key=='request-missing' else -62 if key=='CALL-RAM-exhausted' else -22 if key=='HALO-invalid' else -5)
                    assert c['fw_loaded']==int(key not in ['request-missing','raw-first-error','CALL-RAM-exhausted'])
                    assert len(c['raw_writes'])==(0 if key=='request-missing' else 1 if key=='raw-first-error' else 68)
                    assert any(p['property']=='cirrus,f0-default' and p['value']==[130<<14] for p in c['properties_read'])
                c=subset['boost-control-read-error']
                assert c['register_reads'][-1]==dict(address=0x3804,value=None,result=-5)
                assert len(c['bulk_writes'])==9 and 'cs40l26_bst_ipk_config' in c['entries']
                assert any(w['address']==0x3808 and w['value']==0x40 for w in c['writes'])
                assert any(w['address']==0x3800 and w['value']==0xaa for w in c['writes'])
        if name=='OS4-touch-static-load-order':
            assert result['image_sha256']==image_hash
            assert checks[name]['count']==len(result['cases'])==2
            assert not result['recovery_module_actions']
            assert {c['sample'] for c in result['cases']}=={'os4-current','os4-stable'}
            for case in result['cases']:
                assert case['status']=='PASS'
                assert sha(ROOT/'firmware/samples'/case['sample']/'vendor_boot.img')==case['vendor_boot_sha256']
                check_map(case['stock_second_stage_files'])
                assert all(not a['touch_modules'] for a in case['archives'])
        if name=='stock-ARM64-haptics-PLL-and-chip-identification':
            assert len(result['cases'])==80 and all(c['status']=='PASS' for c in result['cases'])
            assert set(result['drivers'])==set(inspected['profiles'])
            for record in result['drivers'].values():assert sha(ROOT/record['path'])==record['sha256']
        if name=='stock-ARM64-OS2-OS3-haptics-probe-prefix':
            assert result['status']=='PASS' and len(result['profiles'])==4
            assert all(len(profile['cases'])==4 for profile in result['profiles'])
            assert result['hardware_result']=='unverified'
            check_map(result['sources']);check_map(result['tests'])
            for profile in result['profiles']:
                assert sha(ROOT/profile['module'])==profile['module_sha256']
    codec=read(ROOT/checks['archive-codec-pipeline']['evidence'])
    extra={c['name']:c for c in report['additional_checks']}
    for index in range(1,6):
        result=read(ROOT/extra[f'archive-codec-pipeline-repeat-{index}']['evidence'])
        assert result['status']=='PASS' and len(result['cases'])==4
        for field in ['sources','shared_sources','test_sources']:
            assert result[field]==codec[field],(index,field)
            check_map(result[field])
    routes=read(ROOT/checks['multiuser-GUI-routes']['evidence'])
    assert routes['source_sha256']==sha(REC/'gui2/gui2.cpp')
    assert routes['test_sha256']==sha(ROOT/'tests/multiuser_routes_test.py')
    for key,name in [('archive_restore_before_fix','production-archive-restore'),
                     ('raw_image_before_fix','production-raw-image-transfer'),
                     ('operation_feedback_before_fix','operation-completion-feedback'),
                     ('restore_session_before_fix','restore-session-preflight'),
                     ('backup_session_before_fix','backup-session-cancellation'),
                     ('archive_pipeline_before_fix','archive-codec-pipeline'),
                     ('mtp_objects_before_fix','MTP-object-lifecycle'),
                     ('mtp_transfers_before_fix','MTP-transfer-reconciliation'),
                     ('mtp_events_before_fix','MTP-event-lifecycle'),
                     ('usb_init_before_fix','USB-init-configfs-reconciliation'),
                     ('mtp_control_before_fix','MTP-control-framing'),
                     ('mtp_caller_before_fix','MTP-caller-lifecycle'),
                     ('mtp_receiver_before_fix','MTP-storage-receiver')]:
        before=read(ROOT/report[key]['evidence']);after=read(ROOT/checks[name]['evidence'])
        field='test_sources' if 'test_sources' in before else 'tests'
        assert before[field]==after[field],key
        assert len(before['cases'])==len(after['cases'])==report[key]['count'],key
        assert sum(c['status']=='FAIL' for c in before['cases'])==report[key]['failed'],key
        check_map(before['sources'])
    before=read(ROOT/report['mtp_event_completion_before_fix']['evidence'])
    after=read(ROOT/checks['MTP-event-lifecycle']['evidence'])
    assert before['test_sources']==after['test_sources']
    assert len(before['cases'])==6 and all(c['status']=='FAIL' for c in before['cases'])
    passed={c['case'] for c in after['cases'] if c['status']=='PASS'}
    assert {c['case'] for c in before['cases']} <= passed
    check_map(before['sources']);check_map(before['shared_sources'])
    print('PASS: production suites remain source-matched; archive/raw-image/completion/restore/backup/codec/MTP negative controls use the same harnesses.')

    docs=['ADAPTATION-GOALS.md','FEATURE-USAGE.md','MAINTENANCE.md','compatibility-matrix.md',
          'simulation-report.md','docs/HAPTICS-ADAPTATION.md',
          'docs/ARCHIVE-RESTORE-ADAPTATION.md','docs/RAW-IMAGE-ADAPTATION.md',
          'docs/OPERATION-FEEDBACK-ADAPTATION.md','docs/RESTORE-SESSION-ADAPTATION.md',
          'docs/BACKUP-SESSION-ADAPTATION.md','docs/ARCHIVE-PIPELINE-ADAPTATION.md',
          'docs/MTP-OBJECTS-ADAPTATION.md','docs/MTP-ADAPTATION.md','docs/MTP-TRANSFERS-ADAPTATION.md','docs/MTP-EVENTS-ADAPTATION.md',
          'docs/USB-CONFIGFS-ADAPTATION.md','docs/MTP-CONTROL-ADAPTATION.md','docs/PROFILE-SELECTION.md',
          'docs/archive/haptics/HAPTICS-DRIVER-EMULATION.md','docs/archive/haptics/HAPTICS-LIFECYCLE-EMULATION.md','docs/archive/haptics/HAPTICS-WORKER-ADAPTATION.md',
          'docs/archive/haptics/HAPTICS-PLAYBACK-EMULATION.md','docs/archive/haptics/HAPTICS-FIRMWARE-EMULATION.md','docs/OS4-TOUCH-FAILURE.md','docs/MODULE-STATE-ADAPTATION.md']
    for name in docs:
        p=ROOT/name;body=p.read_text()
        for link in re.findall(r'\]\(([^)]+)\)',body):
            if '://' in link or link.startswith('#'):continue
            if link.startswith('</root/AAA/twrp/'):
                assert Path(link[1:-1]).exists(),(name,link)
                continue
            assert (p.parent/link.split('#')[0]).exists(),(name,link)
        if name not in ['FEATURE-USAGE.md','docs/ARCHIVE-RESTORE-ADAPTATION.md','docs/RAW-IMAGE-ADAPTATION.md',
                        'docs/OPERATION-FEEDBACK-ADAPTATION.md','docs/RESTORE-SESSION-ADAPTATION.md',
                        'docs/BACKUP-SESSION-ADAPTATION.md','docs/ARCHIVE-PIPELINE-ADAPTATION.md',
                        'docs/MTP-OBJECTS-ADAPTATION.md','docs/MTP-ADAPTATION.md','docs/MTP-TRANSFERS-ADAPTATION.md','docs/MTP-EVENTS-ADAPTATION.md',
                        'docs/USB-CONFIGFS-ADAPTATION.md','docs/MTP-CONTROL-ADAPTATION.md','docs/PROFILE-SELECTION.md',
                        'docs/archive/haptics/HAPTICS-DRIVER-EMULATION.md','docs/archive/haptics/HAPTICS-LIFECYCLE-EMULATION.md']:
            assert image.name in body,name
    print('PASS: current document links and artifact pointers.')
    print('Recorded goal status:',report['status'],'; outstanding groups:',len(report['not_yet_completed']))
    print('Hardware remains unverified:',', '.join(report['hardware_unverified']))
    print('SHA256',image_hash)

if __name__=='__main__':main()
