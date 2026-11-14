#!/usr/bin/env python3
"""Bind patch0124 job admission wiring, finite regressions and clean delivery."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text())


def entries(p):
    return {e[0]: sha_bytes(e[-1]) for e in ramdisk_entries(boot_parts(Path(p).read_bytes())[1]['ramdisk'])}


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def main():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-shutdown-admission.img'
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
    assert patch['file'] == '0124-shutdown-job-admission.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    for suffix, count, failures in [('current',29,0),('old',29,18),('cli',16,0),('reboot',21,0),('sideload',23,0),('lifecycle',33,0),('drain',4,0)]:
        path = ROOT/f'logs/shutdown-admission-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        reports[suffix] = dict(cases=count, failures=failures, sha256=sha(path))
        if suffix in ['current','old']:
            cases = {c['case']: c for c in report['cases']}
            assert cases['executor-race']['status'] == cases['ticket-release']['status'] == 'PASS'
            assert 'atomic_admission_reservation_race=128' in cases['executor-race']['output']
            assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
            if suffix == 'old':
                assert all(c['status'] == ('FAIL' if c['case'].endswith(('-reserved','-queued')) else 'PASS') for c in report['cases'])
    decrypt = read(ROOT/'logs/multiuser-backend.json')
    assert decrypt['status']=='PASS' and len(decrypt['cases'])==12
    for name, digest in decrypt['sources'].items():
        assert sha(name)==digest, name
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-mtp-receive-boundary.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert changed == ['prop.default','ramdisk-files.sha256sum','system/bin/recovery'], changed
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',scope=__doc__,image_sha256=sha(image),production_sources=len(provenance['files']),jobs=provenance['jobs'],reports=reports,decrypt_cases=12,changed_ramdisk_entries=changed,
                  limits='Host original launch/reboot/CLI/sideload with real tickets/threads/FIFOs/processes and explicit task/DM/HAL/USB/final reboot fixtures. Terminal/direct ORS, complete MTP/USB shutdown and synchronous TEE cancellation unverified. No device operations; full historical OTA reused.')
    (ROOT/'logs/shutdown-admission-delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: patch0124; launch29/old18 failures; CLI16/reboot21/sideload23/lifecycle33/decrypt12/drain4; clean image/six profiles')


if __name__ == '__main__':
    main()
