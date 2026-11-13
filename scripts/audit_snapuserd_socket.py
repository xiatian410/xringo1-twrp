#!/usr/bin/env python3
"""Check original ARM64 SnapshotManager/client socket cleanup evidence, no daemon proof."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    index = json.loads((ROOT/'simulation-report.json').read_text())
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    evidence = ROOT/'logs/ota-snapuserd-socket.json'
    report = json.loads(evidence.read_text())
    assert report['status'] == 'PASS' and report['image_sha256'] == sha(image)
    assert report['fixture_elf_machine'] == 183 and len(report['cases']) == 5
    assert report['snapshot_manager_executed'] and report['snapuserd_socket_connected']
    assert report['hardware_effects_denied'] and not report['full_payload_install']
    for group in ['sources', 'dependencies']:
        for name, digest in report[group].items():
            assert sha(name) == digest, name
    client = '/root/AAA/twrp/system/core/fs_mgr/libsnapshot/snapuserd/snapuserd_client.cpp'
    assert client in report['sources']
    assert any(n.endswith('/libsnapshot_nobinder.a') for n in report['dependencies'])
    cases = {c['name']: c for c in report['cases']}
    assert set(cases) == {'success', 'failure', 'eof', 'closed-peer', 'short-response'}
    for name, case in cases.items():
        assert case['status'] == 'PASS' and case['returncode'] == 0
        output = case['stdout']
        expected = int(name == 'success')
        assert f'result={expected} expected={expected}' in output
        assert f'peer_request={int(name != "closed-peer")}' in output
        assert ('remaining=0 image=0' if expected else 'remaining=3 image=1') in output
        assert 'PASS actual manager/client socket request/response' in output
    ramdisk = {e[0]: e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for name, digest in report['image_entries'].items():
        assert hashlib.sha256(ramdisk[name]).hexdigest() == digest, name
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, evidence_sha256=sha(evidence),
                  image_sha256=sha(image), cases=5, production_changed=False,
                  actual_snapshot_manager=True, actual_snapuserd_client=True,
                  real_socketpair=True, actual_kernel_mapping=False,
                  actual_daemon=False, full_ota_install=False,
                  no_reply_deadline_tested=False, fragmented_success_tested=False,
                  connect_startup_tested=False)
    (ROOT/'logs/snapuserd-socket-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: actual SnapshotManager/client socket5; error/partial cleanup/retry; unchanged image; no daemon claim')


if __name__ == '__main__':
    main()
