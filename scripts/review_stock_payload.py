#!/usr/bin/env python3
"""Review full stock payload evidence; do not rerun the expensive execution."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from acquire_firmware import parse_manifest
from firmware_facts import boot_parts, ramdisk_entries


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(8*1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def main():
    report_path = ROOT/'logs/ota-stock-payload.json'
    r = json.loads(report_path.read_text())
    assert r['status'] == 'PASS' and r['returncode'] == 0
    assert r['fixture_elf_machine'] == 183
    assert r['full_payload_streamed'] and r['original_manifest_unmodified'] and r['original_payload_unmodified']
    assert not r['full_ota_install'] and not r['snapshot_manager_executed'] and not r['postinstall_executed']
    for group in ['sources', 'dependencies']:
        for name, digest in r[group].items():
            assert sha(name) == digest, name
    image = Path(r['image']); assert sha(image) == r['image_sha256']
    entries = {e[0]: e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for name, digest in r['image_entries'].items():
        assert hashlib.sha256(entries[name]).hexdigest() == digest, name
    assert 'system/etc/security/otacerts.zip' in r['image_entries']
    sample = ROOT/'firmware/samples'/r['sample']
    assert sha(sample/'payload-manifest.pb') == r['manifest_sha256']
    manifest = parse_manifest((sample/'payload-manifest.pb').read_bytes())
    stderr = ROOT/'logs/ota-stock-payload.stderr'
    assert sha(stderr) == r['stderr_sha256']
    text = stderr.read_text()
    actual = re.findall(r'Hash of ([A-Za-z0-9_]+): ([A-F0-9]{64})', text)
    expected = {n: p['sha256'].upper() for n, p in manifest['partitions'].items()}
    assert len(actual) == len(expected) and dict(actual) == expected
    assert 'Payload hash matches value in payload.' in text
    assert 'Verifying using certificates: /system/etc/security/otacerts.zip' in text
    assert f"PASS full-stock-payload bytes={r['payload_size']} partitions={len(expected)} opens=10 maps=1 unmaps=1" in r['stdout']
    count = sum(len(p['operations']) for p in manifest['partitions'].values())
    assert f'Completed {count}/{count} operations (100%)' in text
    result = dict(status='PASS', scope=__doc__, report_sha256=sha(report_path),
        image_sha256=r['image_sha256'], payload_bytes=r['payload_size'],
        partitions=len(expected), operations=count, partition_hashes=expected,
        targets_bytes=sum(p['size'] for p in manifest['partitions'].values()),
        full_payload_streamed=True, full_ota_install=False,
        snapshot_manager_executed=False, hardware_testing=False,
        script_sha256=sha(Path(__file__)))
    (ROOT/'logs/ota-stock-payload-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS:', len(expected), 'partition hashes,', count, 'operations, complete payload hash; no real snapshot/boot/postinstall claim')


if __name__ == '__main__': main()
