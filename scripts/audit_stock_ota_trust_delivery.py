#!/usr/bin/env python3
"""Verify fixed OEM trust packaging and real stock ZIP signature acceptance.

ZIP installation still ends at the harmless engine argument checker. This
audit does not establish payload application or complete OTA installation.
"""
import hashlib
import io
import json
from pathlib import Path
import zipfile

from firmware_facts import boot_parts, ramdisk_entries
from prepare_stock_ota_certificate import CERT_SHA256, RECOVERIES
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8*1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def entries(path):
    return {e[0]: e[-1] for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}


def main():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-stock-ota-trust.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem+'-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    log = ROOT/provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    assert log.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in log.read_text()
    cert_report = read(ROOT/'logs/stock-ota-certificate.json')
    assert cert_report['status'] == 'PASS'
    assert cert_report['script_sha256'] == sha(ROOT/'scripts/prepare_stock_ota_certificate.py')
    assert {r['sample']: r['recovery_sha256'] for r in cert_report['sources']} == RECOVERIES
    for sample, digest in RECOVERIES.items():
        source = ROOT/'firmware/samples'/sample/'recovery.img'
        assert sha(source) == digest
        inventory = read(source.parent/'inventory.json')
        assert inventory['partitions']['recovery']['sha256'] == digest
    after = entries(image)
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-media-recreate.img')
    changed = sorted(n for n in set(before)|set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/etc/security/otacerts.zip'], changed
    with zipfile.ZipFile(io.BytesIO(after['system/etc/security/otacerts.zip'])) as z:
        current = {n: z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(io.BytesIO(before['system/etc/security/otacerts.zip'])) as z:
        old = {n: z.read(n) for n in z.namelist()}
    assert current.pop('xiaomi-ota.x509.pem') == (TREE/'security/xiaomi-ota.x509.pem').read_bytes()
    assert sha(TREE/'security/xiaomi-ota.x509.pem') == CERT_SHA256
    assert current == old
    reports = {}
    for name, count in [('zip-stock-os4-fixed', 5), ('zip-stock-trust-host-regression', 36)]:
        path = ROOT/'logs'/(name+'.json')
        report = read(path)
        assert report['status'] == 'PASS' and len(report['cases']) == count
        assert all(c['status'] == 'PASS' for c in report['cases'])
        for key in ['sources', 'binary_dependencies']:
            for file, digest in report[key].items():
                assert sha(file) == digest, file
        if name == 'zip-stock-os4-fixed':
            assert report['image_sha256'] == sha(image)
            assert not report['production_trust_changed'] and not report['full_payload_installed']
            assert report['delivered_trusts_package_certificate']
            rows = {c['name']: c for c in report['cases']}
            for case in ['stock-current-trust', 'stock-package-cert-diagnostic']:
                assert rows[case]['signature_enabled'] and rows[case]['engine_entered']
                assert 'whole-file signature verified' in rows[case]['output']
            assert not rows['stock-without-oem']['engine_entered']
            assert 'failed to verify whole-file signature' in rows['stock-without-oem']['output']
            assert rows['stock-ab-dispatch']['engine_entered']
            assert not rows['stock-device-mismatch']['engine_entered']
            assert 'Package is for product dijun but expected other' in rows['stock-device-mismatch']['output']
        check = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert check['evidence_sha256'] == sha(path)
        reports[name] = dict(cases=count, sha256=sha(path))
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image),
                  production_sources=len(provenance['files']), changed_ramdisk_entries=changed,
                  reports=reports, fixed_oem_certificate_sha256=CERT_SHA256,
                  full_ota_install=False, hardware_testing=False,
                  audit_source_sha256=sha(Path(__file__)))
    (ROOT/'logs/stock-ota-trust-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: fixed OEM trust / unchanged original ZIP signature / removal rejection / native36 / clean808')


if __name__ == '__main__':
    main()
