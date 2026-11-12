#!/usr/bin/env python3
"""Bind MTP object format consistency to native request regressions and the clean image."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, ANDROID, TREE, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    image = ROOT/'imgs/built/recovery-dijun-unified-mtp-format.img'
    sources = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert sources['image_sha256'] == sha(image)
    assert sources['jobs'] == 30
    for name, digest in sources['files'].items():
        assert sha(name) == digest, name
    log = ROOT/sources['build_log']
    assert sha(log) == sources['build_log_sha256']
    text = log.read_text()
    assert 'Deleted images and staging directories' in text
    assert text.count('build completed successfully') == 2
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/mtp-format-final-source.log').read_text()
    def entries(path):
        return {e[0]: (e[1], e[-1]) for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}
    old = entries(ROOT/'imgs/built/recovery-dijun-unified-tool-console.img')
    new = entries(image)
    changed = sorted(n for n in old.keys() | new.keys() if old.get(n) != new.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/lib64/libtwrpmtp-ffs.so']
    assert new['system/lib64/libtwrpmtp-ffs.so'][1] == (ANDROID/'out/target/product/O1_asic/recovery/root/system/lib64/libtwrpmtp-ffs.so').read_bytes()
    reports = {}
    for name in ['mtp-format-objects', 'mtp-format-before', 'mtp-format-transfers']:
        path = ROOT/'logs'/f'{name}.json'
        report = json.loads(path.read_text())
        assert len(report['cases']) == {'mtp-format-objects': 114, 'mtp-format-before': 4, 'mtp-format-transfers': 48}[name]
        for group in ['sources', 'test_sources', 'shared_sources']:
            for file, digest in report[group].items():
                assert sha(file) == digest, file
        expected = 'FAIL' if name == 'mtp-format-before' else 'PASS'
        assert report['status'] == expected
        assert all(case['status'] == expected for case in report['cases'])
        reports[name] = dict(sha256=sha(path), status=expected, cases=len(report['cases']))
    package = json.loads(image.with_suffix('.json').read_text())
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    index = json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256'] == sha(image) and index['status'] == 'in_progress'
    assert len(index['not_yet_completed']) == 12
    assert index['mtp_object_formats']['content_validation'] is False
    result = dict(status='PASS', image=str(image), image_sha256=sha(image),
                  production_sources=len(sources['files']), reports=reports,
                  changed_ramdisk_entries=changed, hardware_testing=False,
                  content_validation=False, scope=__doc__)
    (ROOT/'logs/mtp-format-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: MTP objects114 / transfers48 / old format failures4; clean build /',
          len(sources['files']), 'sources / six profiles; USB and media contents unverified')


if __name__ == '__main__':
    main()
