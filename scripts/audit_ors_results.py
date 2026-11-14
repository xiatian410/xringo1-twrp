#!/usr/bin/env python3
"""Bind original ORS command result propagation to patch0128 delivery."""
import json
from pathlib import Path
from audit_terminal_reap import entries, read, sha
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def main():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-ors-results.img'
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
    assert patch['file'] == '0128-ors-command-error-propagation.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    for suffix, failures in [('current',0),('old',30)]:
        path = ROOT/f'logs/ors-results-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == 58
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
        if suffix=='old':
            assert all(c['status']==('FAIL' if '-failure-' in c['case'] else 'PASS') for c in report['cases'])
            assert any('tail=1 reboots=1' in c['output'] for c in report['cases'] if c['status']=='FAIL')
        else:
            assert all('tail=0 reboots=0' in c['output'] for c in report['cases'] if '-failure-' in c['case'])
        reports[suffix] = dict(cases=58,failures=failures,sha256=sha(path))
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-terminal-shutdown.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert changed == ['prop.default','ramdisk-files.sha256sum','system/bin/recovery'], changed
    package = read(image.with_suffix('.json'))
    assert package['sha256']==sha(image) and len(package['profiles'])==6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',scope=__doc__,image_sha256=sha(image),production_sources=len(provenance['files']),jobs=provenance['jobs'],reports=reports,changed_ramdisk_entries=changed,
                  limits='Host original complete ORS parser/startup action using private files; manager operations, ExecCmd, settings, console, sleeps and final reboot are fixtures. No physical operations, full GUI/FIFO response status, complete ORS shutdown admission, transactional rollback or full OTA. RTC untouched; existing OTA reused.')
    (ROOT/'logs/ors-results-delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: patch0128; ORS58; old30/58 failures; clean image/six profiles')


if __name__ == '__main__':
    main()
