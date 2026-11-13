#!/usr/bin/env python3
"""Bind finite CLI FIFO handshake checks to the clean-built recovery.

No field-refresh root cause, complete ORS/GUI, physical device or full-goal claim.
"""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    image = ROOT/'imgs/built/recovery-dijun-unified-cli-fifo.img'
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert sha(image) == provenance['image_sha256']
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    log = ROOT/provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    text = log.read_text()
    assert 'Deleted images and staging directories' in text
    assert text.count('build completed successfully') == 2
    assert 'recovery clang++ gui2/backend/twrp_background_backend.cpp' in text
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/cli-fifo-final-source.log').read_text()
    spec = json.loads((TREE/'patches/series.json').read_text())['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0077-cli-fifo-nonblocking-handshake.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    for name, failures in [('cli-fifo', 0), ('cli-fifo-before', 7)]:
        path = ROOT/'logs'/f'{name}.json'
        report = json.loads(path.read_text())
        assert len(report['cases']) == 12
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for source, digest in report['sources'].items():
            file = Path(source)
            assert sha(file if file.is_absolute() else ROOT/file) == digest, source
        reports[name] = dict(sha256=sha(path), cases=12, failures=failures)
    def entries(path):
        return {e[0]:(e[1],e[-1]) for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}
    old = entries(ROOT/'imgs/built/recovery-dijun-unified-format-transition.img')
    new = entries(image)
    changed = sorted(n for n in old.keys()|new.keys() if old.get(n)!=new.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery'], changed
    assert b'CLI output reader did not connect; abandoning request' in new['system/bin/recovery'][1]
    assert new['system/bin/recovery'][1] == (ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/recovery').read_bytes()
    package = json.loads(image.with_suffix('.json').read_text())
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    index = json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256'] == sha(image) and index['status'] == 'in_progress'
    assert len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image=str(image), image_sha256=sha(image), production_sources=len(provenance['files']), jobs=provenance['jobs'], reports=reports, changed_ramdisk_entries=changed, hardware_testing=False, field_refresh_root_cause_proven=False)
    (ROOT/'logs/cli-fifo-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: CLI FIFO12 / old7 failures; clean build /',len(provenance['files']),'sources / six profiles; only recovery binary changes')


if __name__=='__main__':
    main()
