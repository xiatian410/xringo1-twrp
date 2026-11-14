#!/usr/bin/env python3
"""Check the touch-only activation fix, its bounded regressions and clean image.

No sysfs/controller callback, physical module loading or OS4.0.5 package is
executed. Changed build.prop bytes model the field-reported identity mismatch.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess

from audit_touch_policy_rollback_delivery import entries, sha
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def main():
    image = ROOT/'imgs/built/yarp-dijun-1.0.1-rc2.img'
    previous = ROOT/'imgs/built/yarp-dijun-1.0.1-rc1.img'
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    for name, target in provenance['symlinks'].items():
        assert os.readlink(name) == target, name
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    build = ROOT/provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    text = build.read_text()
    assert text.count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in text
    header, current = entries(image)
    old_header, old = entries(previous)
    assert sha(previous) == '13644f3443b5baef012920d73838c7e980608235e2478ddbea6334a646f1a082'
    assert image.stat().st_size == previous.stat().st_size == 104857600
    assert header['header_without_ramdisk_size_sha256'] == old_header['header_without_ramdisk_size_sha256']
    changes = sorted(n for n in set(old)|set(current)
                     if (old.get(n) or [None])[-1] != (current.get(n) or [None])[-1])
    expected = ['prop.default', 'ramdisk-files.sha256sum', 'ramdisk-files.txt',
                'system/bin/dijun-runtime.sh', 'system/bin/dijun-select-profile.sh']
    profiles = []
    for p in sorted((TREE/'profiles').glob('*/profile.json')):
        profile = json.loads(p.read_text())
        plan = json.loads((p.parent/'module-sources.json').read_text())
        touch = (p.parent/'touch-modules.plan').read_text().splitlines()
        names = [line.split()[0] for line in touch]
        assert set(names) == set(plan['touch_priority_hard_closure'])
        assert names == [n for n in plan['order'] if n in names]
        for line in touch:
            name, digest, path, deps = line.split()
            source = plan['modules'][name]
            assert digest == source['sha256'] == sha(ROOT/source['source'])
            assert path == source['runtime']
            assert deps == (','.join(source['hard']) or '-')
        files = (p.parent/'touch-files.list').read_text().splitlines()
        assert len(files) == 2
        for line in files:
            digest, mode, path = line.split()
            assert path in ['/lib/firmware/synaptics_spi_dijun.img', '/lib/firmware/dijun_syna_thp_config.ini']
            assert profile['assets'][path.lstrip('/')]['sha256'] == digest
            assert sha(TREE/'prebuilt/common/profile-blobs'/digest) == digest
        for name in ['touch-modules.plan', 'touch-files.list']:
            packaged = f'system/etc/dijun/profiles/{p.parent.name}/{name}'
            assert current[packaged][-1] == (p.parent/name).read_bytes()
            expected.append(packaged)
        profiles.append(dict(profile=p.parent.name, touch_hard_closure=len(names), firmware_files=2))
    assert len(profiles) == 6 and changes == sorted(expected), changes
    inventory_before = set(old['ramdisk-files.txt'][-1].decode().splitlines())
    inventory_after = set(current['ramdisk-files.txt'][-1].decode().splitlines())
    assert inventory_before <= inventory_after
    assert inventory_after - inventory_before == {n for n in expected if n.startswith('system/etc/dijun/profiles/')}
    for p in (TREE/'profiles/runtime').glob('*.sh'):
        assert current['system/bin/'+p.name][-1] == p.read_bytes()
    for name in ['system/bin/recovery', 'system/bin/twrp', 'system/lib64/libgui2.so']:
        assert current[name][-1] == (ANDROID/'out/target/product/O1_asic/recovery/root'/name).read_bytes()
    runtime_path = ROOT/'logs/touch-scope-runtime.json'
    runtime = json.loads(runtime_path.read_text())
    assert runtime['status'] == 'PASS' and runtime['tests_run'] == 5
    assert len(runtime['cases']) == 94 and not runtime['errors'] and not runtime['failures']
    for name, digest in {**runtime['sources'], **runtime['test_sources']}.items():
        path = Path(name) if name.startswith('/') else ROOT/name
        assert sha(path) == digest, name
    # Only the standalone report-output CLI changed during the runtime run.
    # Verify the imported Selection class is identical, retaining original reports.
    selection_source = ROOT/'tests/profile_selection_test.py'
    prior = subprocess.check_output(['git', '-C', str(ROOT.parent/'xringo1-twrp-public'),
                                     'show', '55270529bd62bd645901b6a9ac2f9f2d165ff47c:tests/profile_selection_test.py'])
    def selection_class(source):
        return ast.dump(next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Selection'))
    assert selection_class(prior) == selection_class(selection_source.read_bytes())
    allowed = {hashlib.sha256(prior).hexdigest(), sha(selection_source)}
    for row in runtime['cases']:
        assert row['actual'] == row['expected']
        assert row['test_sources'][str(selection_source)] in allowed
    before_path = ROOT/'logs/touch-scope-before.json'
    before = json.loads(before_path.read_text())
    assert before['status'] == 'FAIL' and len(before['failures']) == 6 and not before['errors']
    assert all(c['expected'] == 0 and c['actual'] == 1 and 'system hash differs' in c['log'] for c in before['cases'])
    selection_path = ROOT/'logs/touch-scope-selection.json'
    selection = json.loads(selection_path.read_text())
    assert selection['status'] == 'PASS' and selection['tests_run'] == 8
    assert selection['selector_sha256'] == sha(TREE/'profiles/runtime/dijun-select-profile.sh')
    result = dict(status='PASS', image=str(image.relative_to(ROOT)), image_sha256=sha(image),
                  image_size=image.stat().st_size, ramdisk_size=header['ramdisk_size'],
                  production_sources=len(provenance['files']), jobs=provenance['jobs'],
                  production_change='Separate exact touch module/firmware closure selection from full crypto identity; platform patches remain at 0139.',
                  profiles=profiles, payload_changes=changes, runtime_groups=5, runtime_phase_calls=94,
                  old_system_mismatch_failures=6, strict_selector_groups=8,
                  strict_selector_cases=len(selection['cases']),
                  evidence={str(p.relative_to(ROOT)):sha(p) for p in [runtime_path,before_path,selection_path]},
                  scope=__doc__, hardware_testing=False,
                  field_touch_status='profile gate fixed in software; current device module/firmware hashes and event delivery unverified',
                  audit_source_sha256=sha(__file__))
    (ROOT/'logs/touch-scope-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
    image.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
