#!/usr/bin/env python3
"""Verify unified packaging independently of the historical OS4-only verifier."""
import hashlib
import json
from pathlib import Path
import stat
import struct
import sys

from firmware_facts import ROOT, SAMPLES, boot_parts, ramdisk_entries, align, digest

TREE=ROOT/'dtsrc/O1_asic_dual'
OUT=Path('/root/AAA/twrp/out/target/product/O1_asic')


def main(path):
    data=path.read_bytes(); header,parts=boot_parts(data)
    entries=ramdisk_entries(parts['ramdisk']); ent={e[0]:e for e in entries}
    assert len(entries)==len(ent), 'duplicate cpio paths'
    assert header['kernel_size']==0 and header['header_version']==4
    assert len(data)==104857600
    samples=sorted(p.parent.name for p in (TREE/'profiles').glob('*/profile.json'))
    for sample in samples:
        original=json.loads((SAMPLES/sample/'analysis/facts.json').read_text())['headers']['recovery']
        assert header['header_without_ramdisk_size_sha256']==original['header_without_ramdisk_size_sha256'], sample
    assert not [p for p in ent if p.endswith('.ko')], 'legacy modules accidentally packaged'
    assert not [p for p in ent if p.startswith('lib/modules/') and Path(p).name in ['modules.load','modules.load.recovery']]
    assert not [p for p in ent if p.startswith('odm/variant/')]
    assert 'system/etc/dijun-crypto-profile.prop' not in ent
    assert not [p for p in ent if p.startswith(('vendor/bin/','vendor/mitee/ta/','system/lib64/mitee/')) and stat.S_ISREG(ent[p][1])], 'fixed OS4 runtime leaked into image'
    for p in (TREE/'profiles/runtime').glob('*.sh'):
        e=ent['system/bin/'+p.name]
        assert stat.S_ISREG(e[1]) and e[-1]==p.read_bytes(),p
    assert b'os4-current|os4-stable)' in ent['system/bin/dijun-runtime.sh'][-1], 'stable activation allowlist missing'
    all_blobs=set()
    profiles={}
    for sample in samples:
        profile=json.loads((TREE/'profiles'/sample/'profile.json').read_text())
        for name in ['selection.conf','runtime-files.list','crypto.prop','modules.plan']:
            assert ent[f'system/etc/dijun/profiles/{sample}/{name}'][-1]==(TREE/'profiles'/sample/name).read_bytes()
        for dest,item in profile['assets'].items():
            sha=item['sha256']; all_blobs.add(sha)
            e=ent['system/etc/dijun/blobs/'+sha]
            assert stat.S_ISREG(e[1]) and digest(e[-1])==sha and len(e[-1])==item['size'],dest
            if dest.startswith('system/etc/vintf/manifest/'):
                assert ent[dest][-1]==e[-1]
        profiles[sample]=dict(kernel_release=profile['kernel_release'],crypto_identity=profile['crypto_identity'],asset_count=len(profile['assets']))
    runtime=ent['system/bin/dijun-runtime.sh'][-1]
    for marker in [b'module_live()',b'wait_module_live()',b'initstate',b'did not become live',b'no reinsertion']:
        assert marker in runtime, 'module lifecycle checks missing'
    props=ent['prop.default'][-1].decode()
    for prop in ['ro.twrp.device_profiles=true','ro.twrp.haptics_frequency=130','ro.twrp.default_timezone=CST-8']:
        assert prop in props,prop
    init=ent['system/etc/init/dijun-mitee.rc'][-1].decode()
    actions=[l.strip() for l in init.splitlines() if l.strip() and not l.lstrip().startswith('#')]
    assert sum(l=='disabled' for l in actions)==3 and sum(l=='oneshot' for l in actions)==3
    assert not any(l.startswith(('interface ','start ')) for l in actions)
    assert sum(l=='setprop twrp.crypto.ready 0' for l in actions)==4
    keystore=ent['system/etc/init/keystore2.rc'][-1]
    assert b'critical' not in b'\n'.join(l for l in keystore.splitlines() if not l.strip().startswith(b'#'))
    fresh={
        'system/bin/recovery':OUT/'recovery/root/system/bin/recovery',
        'system/bin/dijun-wait-services':OUT/'recovery/root/system/bin/dijun-wait-services',
        'system/bin/dijun-usb-config':OUT/'recovery/root/system/bin/dijun-usb-config',
        'system/lib64/libgui2.so':Path('/root/AAA/twrp/out/soong/.intermediates/bootable/recovery/gui2/libgui2/android_recovery_arm64_armv8-a_shared/libgui2.so'),
        'system/lib64/libtwrpmtp-ffs.so':Path('/root/AAA/twrp/out/soong/.intermediates/bootable/recovery/mtp/libtwrpmtp-ffs/android_recovery_arm64_armv8-a_shared/libtwrpmtp-ffs.so'),
        'system/lib64/libtwrpminui.so':OUT/'system/lib64/libtwrpminui.so',
    }
    for name,source in fresh.items():
        assert ent[name][-1]==source.read_bytes(),f'stale or missing {name}'
    for marker in [b'tw_cpu_temp', b'tw_no_cpu_temp', '%d°C'.encode()]:
        assert marker in ent['system/lib64/libgui2.so'][-1], 'temperature GUI missing'
    assert b'dijun USB configuration failed:' in ent['system/bin/dijun-usb-config'][-1]
    helper = ent['system/bin/dijun-usb-config'][-1]
    assert helper[:6] == b'\x7fELF\x02\x01' and ent['system/bin/dijun-usb-config'][1] & 0o111
    phoff = struct.unpack_from('<Q', helper, 32)[0]
    phsize, phnum = struct.unpack_from('<HH', helper, 54)
    assert all(struct.unpack_from('<I', helper, phoff + i * phsize)[0] != 3 for i in range(phnum)), 'helper must not depend on a runtime linker'
    assert b'exec u:r:dijun_usb:s0 root shell usb -- /system/bin/dijun-usb-config' in ent['init.recovery.usb.rc'][-1]
    for name, source in [('init.recovery.usb.rc', TREE/'recovery/root/init.recovery.usb.rc'),
                         ('system/etc/init/hw/init.rc', Path('/root/AAA/twrp/bootable/recovery/etc/init.rc'))]:
        assert ent[name][-1] == source.read_bytes(), f'stale USB configuration: {name}'
    binary=ent['system/bin/recovery'][-1]
    for text in [b'dijun-runtime.sh cache',b'dijun-runtime.sh publish',b'Decryption skipped: no verified, ready device profile',b'Credential request skipped: device crypto profile unavailable']:
        assert text in binary,text
    for text in [b'Cannot access settings: persist storage is not mounted',
                 b'Invalid settings record', b'Settings replaced but directory sync failed',
                 b'Failed to save settings file values']:
        assert text in binary, f'atomic settings fix missing: {text!r}'
    for text in [b'Digest %s failed for', b'Digest replaced but directory sync failed',
                 b'.twrp-digest.XXXXXX']:
        assert text in binary, f'atomic digest publication missing: {text!r}'
    assert b'Cannot enumerate FBE DE users' in binary
    for marker in [b'Invalid extended tar metadata record',
                   b'tar_extract_hardlink(): failed to restore',
                   b'tar_extract_file(): failed to restore Android xattrs']:
        assert marker in binary, f'archive restore fix missing: {marker!r}'
    for marker in [b'Raw image transfer: image exceeds target capacity',
                   b'Raw image transfer: output sync failed',
                   b'Raw image transfer: backup commit failed',
                   b'Raw image transfer cancelled']:
        assert marker in binary, f'raw image transfer fix missing: {marker!r}'
    assert b'Choose a user. Work profiles may use a separate credential.' in ent['system/lib64/libgui2.so'][-1]
    # The bool argument lets keyboard acceptance reuse cancellation without
    # also issuing default BUTTON feedback. Source/patch hashes prove the
    # removed duplicate callbacks and guarded swipe completion separately.
    assert b'_ZN9gui2_core12accept_clickEP11_lv_event_tb' in ent['system/lib64/libgui2.so'][-1]
    # Recovery-backed GUI2 implementations are linked into recovery, while
    # libgui2 contains the abstract UI. Check the owning binary.
    assert b'operation_end: ignoring unmatched completion' in binary
    assert b'GUI2 haptics: background device request failed' in binary
    assert b'GUI2: Haptics device request failed' in ent['system/lib64/libgui2.so'][-1]
    assert b'release_force_feedback' in ent['system/lib64/libtwrpminui.so'][-1]
    for marker in [b'Restore preflight: gap before split archive',
                   b'Restore preflight: target or backup name unavailable',
                   b'Restore preflight: raw image target capacity unavailable or insufficient']:
        assert marker in binary, f'restore session preflight missing: {marker!r}'
    for marker in [b'Backup child failed or was cancelled; metadata not published',
                   b'Unable to remove unfinished backup']:
        assert marker in binary, f'backup session cancellation missing: {marker!r}'
    for marker in [b'TWRP-BACKUP-MANIFEST 1', b'backup incomplete or unsupported inventory',
                   b'required archive part absent', b'.twrp_backup_manifest.tmp']:
        assert marker in binary, f'backup completion manifest missing: {marker!r}'
    for marker in [b'Archive extraction or codec validation failed',
                   b'Archive writer or codec failed before completion']:
        assert marker in binary, f'archive codec pipeline fix missing: {marker!r}'
    for marker in [b'MTP storage rejected: duplicate id or unreadable root',
                   b'MTP rename refused for %s: %s',
                   b'MTP transfer failed from %s to %s: %s',
                   b'MTP inotify overflow: reconciling cached directories',
                   b'MTP interrupt event worker stopped',
                   b'MTP control status: endpoint descriptor unavailable']:
        assert marker in ent['system/lib64/libtwrpmtp-ffs.so'][-1], f'MTP object lifecycle fix missing: {marker!r}'
    assert b'MTP startup was not acknowledged by USB state' in binary
    assert b'MTP shutdown or ADB recovery was not acknowledged' in binary
    assert b'MTP storage message has unterminated strings' in ent['system/lib64/libtwrpmtp-ffs.so'][-1]
    # These are generated build inputs, checked alongside freshly compiled
    # recovery/libgui2 bytes above. They are not a hardware-readout assertion.
    soong_path=Path('/root/AAA/twrp/out/soong/soong.twrp_dijun.variables')
    soong=json.loads(soong_path.read_text())['VendorVars']
    assert soong['twrpGlobalVars']['use_legacy_battery_services']=='true'
    assert soong['twrpGlobalVars']['qcom_rtc_fix'] in ['', 'false']
    assert soong['twrpGlobalVars']['enable_blkdiscard'] in ['', 'false']
    assert soong['twrpVarsPlugin']['TW_CUSTOM_BATTERY_PATH']=='"/sys/class/power_supply/battery"'
    assert soong['twrpVarsPlugin']['TW_CUSTOM_CPU_TEMP_PATH']==''
    assert 'ro.twrp.cpu_temp_type=cpu-crg' in props.splitlines()
    assert b'ro.twrp.cpu_temp_type' in binary
    assert b'/sys/class/power_supply/battery' in binary
    haptics_flags = ['no_haptics', 'tw_haptics_tspdrv', 'tw_support_input_1_2_haptics',
                     'tw_support_input_aidl_haptics', 'tw_support_input_aidl_haptics_fix_off',
                     'tw_use_samsung_haptics']
    assert all(soong['twrpGlobalVars'][key] in ['', 'false'] for key in haptics_flags), 'unexpected haptics backend'
    for marker in [b'No usable FF haptics device: matching names=',
                   b'Force-feedback input directory unavailable:',
                   b'Unable to write haptics node %s:', b'Unable to open haptics node %s:']:
        assert marker in ent['system/lib64/libtwrpminui.so'][-1], f'haptics route fix missing: {marker!r}'
    # OS4 crypto ELF/TA bytes remain exactly the historical verified baseline,
    # even though they now live in a blob store and are activated at runtime.
    baseline=ROOT/'imgs/verified/twrp-recovery-mitee-bootfix.img'
    olddata=baseline.read_bytes(); assert hashlib.md5(olddata).hexdigest()=='5819f969bceb558cf734d5ae5608e211'
    old={e[0]:e for e in ramdisk_entries(boot_parts(olddata)[1]['ramdisk'])}
    os4=json.loads((TREE/'profiles/os4-current/profile.json').read_text())
    preserved=[]
    for dest,item in os4['assets'].items():
        if dest.startswith(('vendor/bin/','vendor/mitee/ta/','system/lib64/mitee/')):
            assert ent['system/etc/dijun/blobs/'+item['sha256']][-1]==old[dest][-1],dest
            preserved.append(dest)
    assert stat.S_ISLNK(ent['etc'][1]) and ent['etc'][-1]==old['etc'][-1]==b'/system/etc'
    for name in ['system/etc/recovery.fstab','system/etc/init/keystore2.rc','system/etc/init/android.hardware.boot-service.xring.recovery.rc']:
        assert ent[name][-1]==old[name][-1],name
    result=dict(image=str(path.resolve()),sha256=digest(data),md5=hashlib.md5(data).hexdigest(),
                size=len(data),ramdisk_size=header['ramdisk_size'],
                aligned_header_ramdisk=4096+align(header['ramdisk_size']),
                padding_and_packaging_budget=len(data)-4096-align(header['ramdisk_size']),
                profiles=profiles,unique_blobs=len(all_blobs),os4_crypto_assets_identical_to_baseline=preserved,
                binary_hashes={n:digest(ent[n][-1]) for n in fresh},
                settings_fix_compiled=True,
                multiuser_discovery_and_selection_compiled=True,
                haptics_runtime_routing_compiled=True,
                gui_haptics_worker_compiled=True,
                ui_feedback_and_cancellation_compiled=True,
                operation_completion_feedback_compiled=True,
                restore_session_preflight_compiled=True,
                backup_session_cancellation_compiled=True,
                backup_completion_manifest_compiled=True,
                digest_atomic_publication_compiled=True,
                archive_codec_pipeline_compiled=True,
                mtp_object_lifecycle_compiled=True,
                mtp_transfer_reconciliation_compiled=True,
                mtp_event_lifecycle_compiled=True,
                mtp_control_framing_compiled=True,
                mtp_caller_lifecycle_compiled=True,
                usb_configfs_reconciliation_compiled=True,
                archive_restore_validation_compiled=True,
                raw_image_transfer_validation_compiled=True,
                raw_image_discard_compiled=False,
                haptics_build_configuration={'backend':'generic FF/LED/timed_output',
                    'cirrus_frequency_hz':130,
                    'flags':{key:soong['twrpGlobalVars'][key] for key in haptics_flags}},
                status_build_configuration={
                    'battery_source':'/sys/class/power_supply/battery',
                    'cpu_temperature_source':'thermal class type=cpu-crg (dynamic ordinal)',
                    'cpu_temperature_gui':'status bar, invalid/disabled hidden, optional on narrow screens',
                    'qcom_rtc_fix':False,
                    'soong_variables_sha256':digest(soong_path.read_bytes())},
                validation='Packaging, provenance and fresh compiled binaries; separate actual-image runtime simulations required. No hardware test.')
    path.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: same recovery header for {len(samples)} samples; no legacy module/runtime overlay; exact manifests/CAS; fresh runtime/core binaries; atomic digests; OS4 crypto bytes preserved')
    print(json.dumps({k:v for k,v in result.items() if k in ['sha256','md5','size','ramdisk_size','padding_and_packaging_budget','unique_blobs']},indent=2))


if __name__=='__main__':main(Path(sys.argv[1]))
