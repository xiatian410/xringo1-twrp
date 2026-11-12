#!/usr/bin/env python3
"""Verify the six-sample Cirrus firmware byte comparison."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    report = json.loads((ROOT / 'logs/haptics-firmware-cross-version-audit.json').read_text())
    assert report['status'] == 'PASS' and report['hardware_result'] == 'unverified'
    assert len(report['samples']) == 6 and len(report['cross_version']) == 7
    for record in report['samples']:
        for firmware in record['firmware'].values():
            odm = firmware['partitions']['odm']
            vendor = firmware['partitions']['vendor']
            assert sha(ROOT / odm['path']) == odm['sha256']
            assert sha(ROOT / vendor['path']) == vendor['sha256']
            assert firmware['odm_vendor_identical'] == (odm['sha256'] == vendor['sha256'])
        assert sha(ROOT / record['module']['path']) == record['module']['sha256']
    for name, check in report['cross_version'].items():
        assert all(check['sha256_by_sample'][s] ==
                   next(r for r in report['samples'] if r['sample'] == s)['firmware'][name]['partitions']['odm']['sha256']
                   for s in check['sha256_by_sample'])
        assert check['identical_across_samples'] == (len(set(check['sha256_by_sample'].values())) == 1)
    for name, digest in report['sources'].items():
        assert sha(ROOT / name) == digest
    test = ROOT / 'tests/haptics_firmware_cross_version_audit.py'
    assert sha(test) == report['tests']['tests/haptics_firmware_cross_version_audit.py']
    assert sha(Path(__file__)) == report['tests']['scripts/audit_haptics_firmware_cross_version.py']
    result = dict(status='PASS', sample_count=6, firmware_count=7,
                  odm_vendor_identical_count=sum(f['odm_vendor_identical']
                      for r in report['samples'] for f in r['firmware'].values()),
                  cross_version_identical_count=sum(x['identical_across_samples']
                      for x in report['cross_version'].values()),
                  source_count=len(report['sources']),
                  conclusion='Firmware bytes agree across extracted samples; runtime loading and hardware remain unverified.')
    (ROOT / 'logs/haptics-firmware-cross-version-audit-verification.json').write_text(
        json.dumps(result, indent=2) + '\n')
    print('PASS: six sample firmware hashes, ODM/vendor relations and bound sources')


if __name__ == '__main__':
    main()
