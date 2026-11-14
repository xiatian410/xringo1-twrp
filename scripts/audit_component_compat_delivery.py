#!/usr/bin/env python3
"""Bind independent feature activation to original components and a clean image.

Host activation substitutes mounts, properties, insmod, input and Binder. This
audit does not establish physical decryption, haptics or future OTA compatibility.
"""
import json
import os
from pathlib import Path

from audit_touch_policy_rollback_delivery import entries, sha
from sync_device_tree import ANDROID, ROOT, TREE, manifest


def check_report(name, groups, image_hash=None):
    path = ROOT / 'logs' / name
    report = json.loads(path.read_text())
    assert report['status'] == 'PASS' and report['tests_run'] == groups, name
    assert report['image_sha256'] == image_hash, name
    assert not report['errors'] and not report['failures'], name
    for source, digest in {**report['sources'], **report['test_sources']}.items():
        assert sha(ROOT / source) == digest, source
    for row in report['cases']:
        assert row['actual'] == row['expected'], row
    return report


def main():
    image = ROOT / 'imgs/built/yarp-dijun-1.0.1-rc3.img'
    previous = ROOT / 'imgs/built/yarp-dijun-1.0.1-rc2.img'
    provenance = json.loads(image.with_name(image.stem + '-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    for name, target in provenance['symlinks'].items():
        assert os.readlink(name) == target, name
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    build = ROOT / provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    text = build.read_text()
    assert text.count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in text
    header, current = entries(image)
    old_header, old = entries(previous)
    assert sha(previous) == 'd6d07213e0540b7862b50a90f57658e619e6be1108961f84e87fad335fd9545b'
    assert image.stat().st_size == previous.stat().st_size == 104857600
    assert header['kernel_size'] == 0 and header['header_version'] == 4
    assert header['header_without_ramdisk_size_sha256'] == old_header['header_without_ramdisk_size_sha256']
    changed = sorted(n for n in set(old) | set(current)
                     if (old.get(n) or [None])[-1] != (current.get(n) or [None])[-1])
    expected = ['prop.default', 'ramdisk-files.sha256sum', 'ramdisk-files.txt',
                'system/bin/dijun-runtime.sh', 'system/bin/dijun-select-profile.sh']
    profiles = []
    for path in sorted((TREE / 'profiles').glob('*/profile.json')):
        profile = json.loads(path.read_text())
        plan = json.loads((path.parent / 'module-sources.json').read_text())
        counts = {}
        for component in ['touch', 'haptics', 'crypto']:
            lines = (path.parent / f'{component}-modules.plan').read_text().splitlines()
            names = [line.split()[0] for line in lines]
            assert set(names) == set(plan['runtime_component_closures'][component])
            assert set(plan[f'{component}_priority_hard_closure']) <= set(names)
            for line in lines:
                name, digest, source, deps = line.split()
                record = plan['modules'][name]
                assert source == record['runtime']
                assert digest == record['sha256'] == sha(ROOT / record['source'])
                assert deps == (','.join(record['hard']) or '-')
                for dep in record['hard']:
                    assert names.index(dep) < names.index(name)
            checks = (path.parent / f'{component}-checks.list').read_text().splitlines()
            for line in checks:
                digest, source = line.split()
                stock = ROOT / 'firmware/samples' / path.parent.name / 'analysis' / source.lstrip('/')
                assert sha(stock) == digest
            assets = (path.parent / f'{component}-files.list').read_text().splitlines()
            for line in assets:
                digest, mode, target = line.split()
                record = profile['assets'][target.lstrip('/')]
                assert digest == record['sha256'] and int(mode, 8) == int(record['mode'], 8)
                assert sha(TREE / 'prebuilt/common/profile-blobs' / digest) == digest
            counts[component] = dict(modules=len(names), assets=len(assets), installed_checks=len(checks))
        assert {'fbe', 'xr_ufs', 'xr_rpmb', 'mitee'} <= set(plan['crypto_priority_hard_closure'])
        for name in ['crypto-layout.conf', 'crypto-release.conf', 'modules.plan'] + [
                f'{c}-{n}' for c in ['touch', 'haptics', 'crypto']
                for n in ['files.list', 'modules.plan', 'checks.list']]:
            packaged = f'system/etc/dijun/profiles/{path.parent.name}/{name}'
            assert current[packaged][-1] == (path.parent / name).read_bytes()
            if packaged not in old or old[packaged][-1] != current[packaged][-1]:
                expected.append(packaged)
        profiles.append(dict(profile=path.parent.name, components=counts))
    assert len(profiles) == 6 and changed == sorted(expected), changed
    # The field-confirmed raw0 helper and all platform binaries/assets retain
    # their rc2 bytes; only the two orchestration scripts and manifests change.
    for name in ['system/bin/dijun-touch-reports.sh', 'system/bin/recovery',
                 'system/bin/twrp', 'system/lib64/libgui2.so']:
        assert current[name][-1] == old[name][-1], name
    for path in (TREE / 'profiles/runtime').glob('*.sh'):
        assert current['system/bin/' + path.name][-1] == path.read_bytes()
    runtime = check_report('component-compat-runtime.json', 13)
    packaged = check_report('component-compat-image.json', 1, sha(image))
    assert len(packaged['cases']) == 18
    before = json.loads((ROOT / 'logs/component-compat-before.json').read_text())
    assert before['status'] == 'FAIL' and len(before['failures']) == 6
    assert not before['errors'] and before['image_sha256'] == sha(previous)
    assert len(before['cases']) == 6
    selection = json.loads((ROOT / 'logs/component-compat-selection.json').read_text())
    assert selection['status'] == 'PASS' and selection['tests_run'] == 8
    assert selection['selector_sha256'] == sha(TREE / 'profiles/runtime/dijun-select-profile.sh')
    result = dict(status='PASS', image=str(image.relative_to(ROOT)), image_sha256=sha(image),
                  image_size=image.stat().st_size, ramdisk_size=header['ramdisk_size'],
                  production_sources=len(provenance['files']), jobs=provenance['jobs'],
                  production_change='Independent touch/haptics/crypto component selection; current active-slot release/SPL; unchanged platform patches through 0139.',
                  profiles=profiles, payload_changes=changed,
                  runtime_groups=13, runtime_phase_calls=len(runtime['cases']),
                  packaged_groups=1, packaged_phase_calls=len(packaged['cases']),
                  previous_image_feature_regressions=6,
                  strict_selector_groups=8, strict_selector_cases=len(selection['cases']),
                  field_touch='User confirmed rc2 touch normal; rc3 raw0 helper and input binaries unchanged.',
                  field_crypto_and_haptics='User reported absent on rc2; rc3 software activation fixed, hardware outcome unverified.',
                  hardware_testing=False, scope=__doc__,
                  evidence={name: sha(ROOT / name) for name in [
                      'logs/component-compat-runtime.json', 'logs/component-compat-image.json',
                      'logs/component-compat-before.json', 'logs/component-compat-selection.json']},
                  audit_source_sha256=sha(__file__))
    (ROOT / 'logs/component-compat-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    image.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    image.with_suffix('.img.sha256').write_text(f'{sha(image)}  {image.name}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
