#!/usr/bin/env python3
"""Check original RTC callback evidence, provenance and current image bindings."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    index = json.loads((ROOT/'simulation-report.json').read_text())
    path = ROOT/'logs/rtc-driver-emulation.json'
    report = json.loads(path.read_text())
    image = Path(index['image'])
    production = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert sha(image) == index['image_sha256'] == report['image_sha256'] == production['image_sha256']
    assert len(production['files']) == report['production_sources'] == 765
    for bindings in [production['files'], report['sources'], report['modules']]:
        for name, digest in bindings.items():
            assert sha(Path(name)) == digest, name
    assert report['status'] == 'PASS' and len(report['cases']) == 56
    profiles = ['os2-initial', 'os2-final', 'os3-initial', 'os3-final', 'os4-current', 'os4-stable']
    assert sorted(o['profile'] for o in report['origins']) == sorted(profiles)
    for profile in profiles:
        origin = next(o for o in report['origins'] if o['profile'] == profile)
        assert origin['byte_match'] and origin['entry'].endswith('/dw_apb_rtc.ko')
        module = next(p for p in report['modules'] if f'/{profile}/' in p)
        assert report['modules'][module] == origin['module_sha256']
        cases = {c['case']: c for c in report['cases'] if c['profile'] == profile}
        labels = {'read-zero', 'read-utc', 'read-divider', 'read-wrap', 'read-zero-frequency',
                  'set-success', 'set-pmic-failure', 'set-alarm-adjust'}
        if profile.startswith('os4-'):
            labels |= {'refresh-success', 'refresh-pmic-failure', 'refresh-assert-failure', 'refresh-deassert-failure'}
        assert set(cases) == labels and all(c['status'] == 'PASS' for c in cases.values())
        assert cases['read-wrap']['seconds'] == 32 and cases['read-zero-frequency']['seconds'] == 0
        assert cases['set-pmic-failure']['rc'] == -5
        assert cases['set-pmic-failure']['saved'] == cases['set-success']['saved']
        if profile.startswith('os4-'):
            assert cases['refresh-pmic-failure']['rc'] == 0
            assert cases['refresh-pmic-failure']['writes'][2]['value'] == 173
            assert cases['refresh-assert-failure']['rc'] == cases['refresh-deassert-failure']['rc'] == -5
    assert any(c.get('evidence') == 'logs/rtc-driver-emulation.json' and
               c['evidence_sha256'] == sha(path) for c in index['additional_checks'])
    assert report['production_changes'] is False and index['status'] == 'in_progress'
    assert len(index['not_yet_completed']) == 12
    result = dict(status='PASS', count=56, original_vendor_boot_origins=6,
                  image_sha256=sha(image), production_sources=765, evidence_sha256=sha(path),
                  audit_source_sha256=sha(Path(__file__)),
                  scope='Original RTC callbacks with explicit MMIO/PMIC/calendar fixtures; no full boot/hctosys/drift verification.')
    (ROOT/'logs/rtc-driver-emulation-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: 56 RTC cases, six original ramdisk origins, 765 production sources; full12 open.')


if __name__ == '__main__':
    main()
