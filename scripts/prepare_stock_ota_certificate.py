#!/usr/bin/env python3
"""Prepare one fixed OEM OTA certificate from hash-pinned stock recoveries.

Never read a certificate from the ZIP being installed. Only local, ordinary
stock recovery images with the six recorded hashes are accepted. No private
key is required or generated. The extracted public certificate stays local.
"""
import hashlib
import io
import json
from pathlib import Path
import stat
import zipfile

from firmware_facts import boot_parts, ramdisk_entries

ROOT = Path(__file__).resolve().parents[1]
CERT_SHA256 = 'ff85d8bc50e4eed4c5f54734b20003e845a8ee5f206bfe717335ad594dd01a5e'
RECOVERIES = {
    'os2-initial': 'f8c9d3c426486ac9af8936d85cf74b4f8e7c8f7f9949e7ffb41862ce00484957',
    'os2-final': '8ef5f1241ec1e2f99442b7d92bcb24ee206bf10a43f367a2235bf28214dba7b4',
    'os3-initial': '803eff288949c41a75fb78822c16dc17c3f6c3f5ba68729065499f3a3f35bc87',
    'os3-final': '4c3782e8d3c6be334e13c5bcf40fcd635816b4e7f2f4ef636074126c99847ba5',
    'os4-current': '3bbd522941c598e366c26e5231ca76eed037d6278a985deb2fe52397b55db17e',
    'os4-stable': '6b09247cea7869b66b383009a28b77160c42afb0be90d6c143eca2d7c253b629',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    rows = []
    certificate = None
    for sample, expected in RECOVERIES.items():
        path = ROOT/'firmware/samples'/sample/'recovery.img'
        assert not path.is_symlink() and stat.S_ISREG(path.stat().st_mode), path
        data = path.read_bytes()
        assert sha(data) == expected, f'Unrecognized stock recovery: {sample}'
        records = [e for e in ramdisk_entries(boot_parts(data)[1]['ramdisk'])
                   if e[0] == 'system/etc/security/otacerts.zip']
        assert len(records) == 1 and stat.S_ISREG(records[0][1])
        archive = records[0][-1]
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            assert len(z.infolist()) == 1
            cert = z.read(z.infolist()[0])
        assert sha(cert) == CERT_SHA256 and cert.startswith(b'-----BEGIN CERTIFICATE-----')
        assert certificate is None or cert == certificate
        certificate = cert
        rows.append(dict(sample=sample, recovery_sha256=expected,
                         otacerts_sha256=sha(archive), certificate_sha256=sha(cert)))
    dest = ROOT/'dtsrc/O1_asic_dual/security/xiaomi-ota.x509.pem'
    assert not dest.is_symlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.read_bytes() != certificate:
        temporary = dest.with_suffix('.tmp')
        with temporary.open('xb') as f:
            f.write(certificate)
        temporary.replace(dest)
    report = dict(status='PASS', certificate_sha256=CERT_SHA256, sources=rows,
                  destination=str(dest), trust_policy='Fixed build-time OEM key; no package-supplied runtime trust',
                  script_sha256=sha(Path(__file__).read_bytes()))
    (ROOT/'logs').mkdir(exist_ok=True)
    (ROOT/'logs/stock-ota-certificate.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS: same fixed OEM OTA certificate from six hash-pinned stock recoveries')


if __name__ == '__main__':
    main()
