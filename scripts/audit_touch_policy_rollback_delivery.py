#!/usr/bin/env python3
"""Bind the exact touch timing rollback to its clean candidate, without hardware claims."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entries(path):
    header, parts = boot_parts(path.read_bytes())
    rows = ramdisk_entries(parts['ramdisk'])
    result = {row[0]: row for row in rows}
    assert len(rows) == len(result)
    return header, result


def main():
    image = ROOT/'imgs/built/yarp-dijun-1.0.1-rc1.img'
    previous = ROOT/'imgs/built/yarp-dijun-1.0.0.img'
    script = TREE/'profiles/runtime/dijun-touch-reports.sh'
    rel = str(script.relative_to(ROOT))
    baseline = subprocess.check_output(['git', '-C', str(ROOT.parent/'xringo1-twrp-public'),
                                       'show', '022963b94e10f6e885778f63b54c809f28ee2783^:'+rel])
    assert script.read_bytes() == baseline
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
    assert sha(previous) == '4623448c6b0a986ca3cb056383eeb7b9ad91a54181b40e920622e863104880bd'
    assert image.stat().st_size == previous.stat().st_size == 104857600
    assert header['header_without_ramdisk_size_sha256'] == old_header['header_without_ramdisk_size_sha256']
    assert header['kernel_size'] == 0 and header['header_version'] == 4
    changes = sorted(name for name in set(old)|set(current)
                     if (old.get(name) or [None])[-1] != (current.get(name) or [None])[-1])
    assert changes == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/dijun-touch-reports.sh'], changes
    assert current['system/bin/dijun-touch-reports.sh'][-1] == baseline
    assert len([n for n in current if n.startswith('system/etc/dijun/profiles/') and n.endswith('/selection.conf')]) == 6
    for name in ['system/bin/recovery', 'system/bin/twrp', 'system/lib64/libgui2.so']:
        assert current[name][-1] == (ANDROID/'out/target/product/O1_asic/recovery/root'/name).read_bytes()
    policy_path = ROOT/'logs/touch-policy-rollback.json'
    policy = json.loads(policy_path.read_text())
    assert policy['status'] == 'PASS' and policy['count'] == len(policy['cases']) == 7
    for name, digest in policy['sources'].items():
        assert sha(name) == digest, name
    assert "('raw-one', 1, 0)" in (ROOT/'logs/touch-policy-rollback-before.log').read_text()
    result = dict(status='PASS', image=str(image.relative_to(ROOT)), image_sha256=sha(image),
                  previous_image_sha256=sha(previous), image_size=image.stat().st_size,
                  ramdisk_size=header['ramdisk_size'], production_sources=len(provenance['files']),
                  production_change='Exact rollback of the nine-line touch settle-window addition in 022963b; native maintained device-tree script. Platform patch sequence remains at 0139.',
                  touch_script_sha256=sha(script), jobs=provenance['jobs'], policy_cases=7,
                  policy_report_sha256=sha(policy_path), payload_changes=changes,
                  baseline_commit='022963b94e10f6e885778f63b54c809f28ee2783^',
                  hardware_testing=False, field_touch_status='user-reported-failure; rollback-candidate-not-device-validated',
                  scope=__doc__, limits='Private filesystem fixtures verify readiness polling, immediate single raw0 request and errors. They do not execute sysfs callbacks, the controller or physical input. The two-second delay is not a proven fault cause.',
                  audit_source_sha256=sha(__file__))
    (ROOT/'logs/touch-policy-rollback-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    image.with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
