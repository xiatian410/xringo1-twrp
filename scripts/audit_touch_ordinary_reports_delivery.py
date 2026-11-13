#!/usr/bin/env python3
"""Bind the ordinary-touch-report startup policy to its clean image.

The audit checks source provenance and ramdisk packaging only. It does not
claim that a controller accepted the request or produced physical events.
"""
import hashlib
import json
from pathlib import Path

from firmware_facts import ROOT, boot_parts, ramdisk_entries
from sync_device_tree import ANDROID, TREE, manifest


IMAGE = ROOT / 'imgs/built/recovery-dijun-unified-ordinary-reports.img'
SCRIPT = TREE / 'profiles/runtime/dijun-touch-reports.sh'
REPORT = ROOT / 'logs/touch-report-policy-test.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    image_sha = sha(IMAGE)
    sources = json.loads(IMAGE.with_name(IMAGE.stem + '-sources.json').read_text())
    assert sources['image_sha256'] == image_sha
    assert len(sources['files']) == 809
    assert sources['jobs'] == 30
    build_log = ROOT / sources['build_log']
    build_text = build_log.read_text()
    assert build_text.count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build_text
    for path, digest in sources['files'].items():
        assert sha(path) == digest, path
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')

    _, parts = boot_parts(IMAGE.read_bytes())
    entries = {item[0]: item[-1] for item in ramdisk_entries(parts['ramdisk'])}
    assert entries['system/bin/dijun-touch-reports.sh'] == SCRIPT.read_bytes()
    runtime = entries['system/bin/dijun-runtime.sh']
    assert b'timeout -s KILL 6 sh "$root/system/bin/dijun-touch-reports.sh" "$root"' in runtime
    assert b'twrp.profile.touch_reports' in runtime

    policy = json.loads(REPORT.read_text())
    assert policy['status'] == 'PASS' and policy['count'] == 9
    assert all(case['status'] == 'PASS' for case in policy['cases'])

    result = {
        'status': 'PASS',
        'image': str(IMAGE),
        'image_sha256': image_sha,
        'production_sources': len(sources['files']),
        'policy_cases': policy['count'],
        'profiles': 6,
        'build_jobs': sources['jobs'],
        'hardware_testing': False,
        'scope': __doc__,
        'limitations': 'A sysfs request and readback do not prove controller mode or input event delivery.',
    }
    (ROOT / 'logs/touch-ordinary-reports-delivery.json').write_text(
        json.dumps(result, indent=2) + '\n'
    )
    print('PASS: ordinary-report policy packaged; 809 sources; 9 fixture cases; hardware unverified')


if __name__ == '__main__':
    main()
