#!/usr/bin/env python3
"""Extract bounded facts from the user-provided OS4.0.4 recovery log bundle."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'imgs/built/1/os4-touch-20261112-000013.zip'
LIVE_GETEVENT = ROOT / 'imgs/built/1/os4-touch-getevent-live.txt'
INTERRUPTS = ROOT / 'imgs/built/1/interrupts.txt'
OUTPUT = ROOT / 'logs/os4-stable-haptics-runtime-observation.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    return data.decode('utf-8-sig', errors='replace')


def main():
    with ZipFile(BUNDLE) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    required = {'getprop.txt', 'modules.txt', 'input-devices.txt', 'dev-input.txt',
                'getevent-capabilities.txt', 'recovery.log', 'dmesg.txt', 'logcat.txt'}
    assert required <= files.keys()
    text = {name: decode(data) for name, data in files.items()}
    prop = text['getprop.txt']
    modules = text['modules.txt']
    inputs = text['input-devices.txt']
    nodes = text['dev-input.txt']
    capabilities = text['getevent-capabilities.txt']
    recovery = text['recovery.log']
    runtime = decode(files.get('dijun-runtime.log', b''))
    live_getevent = decode(LIVE_GETEVENT.read_bytes())
    interrupts = decode(INTERRUPTS.read_bytes())
    logcat = text['logcat.txt']

    assert '[twrp.profile.selected]: [os4-stable]' in prop
    assert '[twrp.profile.modules]: [complete]' in prop
    assert '[twrp.profile.haptics_input]: [registered]' in prop
    assert 'xring_audio_hw_third ' in modules and ' Live ' in modules
    assert 'Name="cs40l26_input"' in inputs
    assert '/i2c-0/0-0043/input/input4' in inputs
    assert 'FF=124020000 0' in inputs
    assert 'event4' in nodes and 'root input' in nodes
    assert 'name:     "cs40l26_input"' in capabilities
    assert all(name in capabilities for name in ('FF_PERIODIC', 'FF_SINE', 'FF_CUSTOM', 'FF_GAIN'))
    assert 'Using force-feedback haptics at /dev/input/event4 (cs40l26_input), effect type 81' in recovery
    assert 'runtime modules: complete' in runtime
    assert 'runtime haptics input: registered' in runtime
    assert 'runtime cache: verified os4-stable' in runtime
    assert '[ro.twrp.haptics_frequency]: [130]' in prop

    selftest = json.loads((ROOT / 'logs/haptics-probe-selftest-emulation.json').read_text())
    assert selftest['status'] == 'PASS'
    stable_selftest = [case for case in selftest['cases']
                       if case.get('sample') == 'os4-stable'
                       and case['case'] == 'start-before-erase']
    assert len(stable_selftest) == 1
    selftest_case = stable_selftest[0]
    assert selftest_case['workers'] == ['cs40l26_upload_worker',
                                        'cs40l26_vibe_start_worker',
                                        'cs40l26_erase_worker']
    assert selftest_case['selftest_mailbox'] == [{'command': 0x01800081, 'result': 0}]

    touch_present = 'Name="Xiaomi_Touch_Input_0"' in inputs
    touch_event_trace = 'EV_ABS' in live_getevent or 'ABS_MT_' in live_getevent
    irq_lines = [line for line in interrupts.splitlines()
                 if 'cs40l26 IRQ1 Controller' in line]
    primary_irq = next((line for line in irq_lines if 'xr-dwapb-gpio' in line), None)
    mailbox_irq = next((line for line in irq_lines if 'Mailbox interrupt' in line), None)
    synaptics_irq = next((line for line in interrupts.splitlines()
                          if 'xiaomi_tpsynaptics_tcm' in line), None)
    assert touch_present and primary_irq and mailbox_irq and synaptics_irq
    firmware_rootfs_avcs = [line for line in logcat.splitlines()
                             if 'avc:  denied' in line and '/lib/firmware/cs40l26-' in line]
    adaptive_property_avcs = [line for line in logcat.splitlines()
                              if 'avc:  denied' in line and 'adaptive_haptics_prop' in line]
    assert firmware_rootfs_avcs and adaptive_property_avcs
    assert all('permissive=1' in line for line in firmware_rootfs_avcs + adaptive_property_avcs)

    firmware_names = sorted(path.name for path in
                            (ROOT / 'firmware/samples/os4-stable/analysis/odm/firmware')
                            .glob('cs40l26*'))
    assert len(firmware_names) == 9
    firmware_hashes = {}
    for sample in ['os2-initial', 'os2-final', 'os3-initial', 'os3-final',
                   'os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis/odm/firmware'
        firmware_hashes[sample] = {name: sha((base / name).read_bytes()) for name in firmware_names}
    assert all(hashes == firmware_hashes['os4-stable'] for hashes in firmware_hashes.values())
    policy_path = Path('/root/AAA/twrp/system/sepolicy/private/twrp.te')
    policy = policy_path.read_text()
    assert 'permissive recovery;' in policy

    report = {
        'status': 'PASS',
        'scope': 'Read-only parsing of a user-provided recovery log bundle. PASS means the listed observations are present; it is not a vibration or touch functional test.',
        'bundle': str(BUNDLE.relative_to(ROOT)),
        'bundle_sha256': sha(BUNDLE.read_bytes()),
        'files': {name: sha(data) for name, data in sorted(files.items())},
        'related_stock_probe_selftest_evidence': {
            'path': 'logs/haptics-probe-selftest-emulation.json',
            'sha256': sha((ROOT / 'logs/haptics-probe-selftest-emulation.json').read_bytes()),
            'scope': 'Original-code host emulation only; not evidence that this runtime IRQ snapshot came from the self-test.',
        },
        'policy_context': {
            'path': str(policy_path),
            'sha256': sha(policy_path.read_bytes()),
            'recovery_domain_permissive': True,
            'firmware_rootfs_avc_count': len(firmware_rootfs_avcs),
            'adaptive_haptics_property_avc_count': len(adaptive_property_avcs),
            'avc_interpretation': 'Permissive audit observations; not proof that copy or property read failed.',
        },
        'supplemental_files': {
            str(LIVE_GETEVENT.relative_to(ROOT)): sha(LIVE_GETEVENT.read_bytes()),
            str(INTERRUPTS.relative_to(ROOT)): sha(INTERRUPTS.read_bytes()),
        },
        'observations': {
            'selected_profile': 'os4-stable',
            'profile_cache_verified': True,
            'module_phase': 'complete',
            'haptics_module_live': 'xring_audio_hw_third' in modules and ' Live ' in modules,
            'input_name': 'cs40l26_input',
            'input_sysfs': '/devices/platform/soc/ec100000.i2c/i2c-0/0-0043/input/input4',
            'input_device': '/dev/input/event4',
            'input_node_permissions': 'root:input 0660',
            'ff_capabilities': ['FF_PERIODIC', 'FF_SINE', 'FF_CUSTOM', 'FF_GAIN'],
            'recovery_selected_periodic_effect': True,
            'recovery_haptics_frequency_hz': 130,
            'avc_mode': 'permissive',
            'rootfs_firmware_copy_denial_proven': False,
            'adaptive_property_read_denial_proven': False,
            'six_profiles_have_identical_nine_file_odm_firmware': True,
            'os2_os3_os4_firmware_sha256': firmware_hashes,
            'touch_input_registered': touch_present,
            'live_getevent_contains_touch_event_records': touch_event_trace,
            'synaptics_irq_snapshot': synaptics_irq.strip(),
            'synaptics_irq_count_unrelated_snapshot': int(synaptics_irq.split()[1]),
            'primary_irq_snapshot': primary_irq.strip(),
            'mailbox_irq_snapshot': mailbox_irq.strip(),
            'stock_probe_contains_start_selftest': True,
            'stock_probe_selftest_start_mailbox': '0x01800081',
            'mailbox_irq_may_be_startup_selftest': True,
            'selftest_irq_correlation_proven': False,
        },
        'not_observed': [
            'EVIOCSFF upload return value and errno for an actual haptic request',
            'EV_FF playback write return value and errno',
            'input-event trace correlated with a user haptic request',
            'before/after IRQ counter delta for a user haptic request',
            'DSP running state or physical motor response',
            'touch ABS_MT event records or visible touch response',
        ],
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: OS4 stable module, input node, FF capabilities and Recovery selection are present.')
    print(f"OBSERVED: Synaptics IRQ cumulative snapshot={int(synaptics_irq.split()[1])}; not correlated with touch.")
    print('OBSERVED: profile cache verified; six profiles share identical nine-file ODM firmware; AVCs are permissive.')
    print('LIMIT: no touch-correlated IRQ delta/event trace or user-request-correlated FF result.')


if __name__ == '__main__':
    main()
