#!/usr/bin/env python3
"""Bind bounded restore-sidecar regression evidence to patch0126 delivery."""
import json
from pathlib import Path
from audit_terminal_reap import entries, read, sha
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def main():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-digest-preflight.img'
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
    assert patch['file'] == '0126-restore-digest-bounded-read.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    summaries = {}
    for suffix, count, failures in [('current',66,0),('old',7,7)]:
        path = ROOT/f'logs/digest-sidecar-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for group in ['sources','shared_sources','test_sources']:
            for name, digest in report[group].items():
                assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
        cases = {c['case']: c for c in report['cases']}
        if suffix == 'old':
            assert sum(c['returncode']==124 for c in cases.values()) == 5
        else:
            for name in ['digest-limit','digest-symlink','digest-no-sidecar','second-fifo-sidecar','second-oversized-sidecar']:
                assert cases[name]['status']=='PASS'
        summaries[suffix] = dict(cases=count,failures=failures,sha256=sha(path))
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-terminal-reap.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert changed == ['prop.default','ramdisk-files.sha256sum','system/bin/recovery'], changed
    package = read(image.with_suffix('.json'))
    assert package['sha256']==sha(image) and len(package['profiles'])==6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',scope=__doc__,image_sha256=sha(image),production_sources=len(provenance['files']),
                  jobs=provenance['jobs'],reports=summaries,changed_ramdisk_entries=changed,
                  limits='Host original restore planning/raw-copy/digest with BoringSSL and private file I/O; mounts, device metadata/ioctl, archive extraction, GUI and Android services remain fixtures. No authentication, concurrent source stability, physical I/O deadline or full OTA claim.')
    (ROOT/'logs/digest-sidecar-delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: patch0126; restore66; old7/7 failures (five FIFO timeouts); clean image/six profiles')


if __name__ == '__main__':
    main()
