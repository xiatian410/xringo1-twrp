#!/usr/bin/env python3
"""Bind original ARM64 postinstall child lifecycle evidence to unchanged delivery."""
import hashlib
import json
from pathlib import Path
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = ROOT/'logs/ota-postinstall-program.json'
    r = json.loads(path.read_text())
    assert r['status'] == 'PASS' and len(r['cases']) == 9
    assert r['fixture_elf_machine'] == r['child_elf_machine'] == 183
    assert r['original_postinstall'] and r['original_subprocess']
    assert r['mount_boundary'] and not r['snapshot_manager_executed']
    assert not r['production_fix'] and not r['full_payload_install']
    for group in ['sources', 'dependencies']:
        for name, digest in r[group].items():
            assert sha(name) == digest, name
    names = ['normal','exit7','optional-exit7','exit3','exit4','signal15','missing-program','mount-fail','cancel']
    assert [c['name'] for c in r['cases']] == names
    for case in r['cases']:
        name, output = case['name'], case['stdout']
        assert 'PASS actual ARM64 child and original parent lifecycle' in output
        ok = name in ['normal', 'optional-exit7']
        assert f'finishes={int(ok)} switches={int(ok)}' in output
        if name == 'cancel':
            assert 'done=0 stopped=1' in output
        else:
            code = 0 if ok else {'exit3':19, 'exit4':43, 'mount-fail':63}.get(name,5)
            assert f'done=1 stopped=0 code={code}' in output
        if name in ['exit7', 'optional-exit7', 'exit3', 'exit4']:
            assert 'exited with si_status: '+name[-1] in case['stderr']
        if name == 'signal15':
            assert 'terminated with si_code 2' in case['stderr']
    assert len(r['stock_postinstall']) == 6
    for sample in r['stock_postinstall']:
        expected = ([dict(partition='system', run=True, path='system/bin/otapreopt_script', optional=True)]
                    if sample['sample'].startswith('os4-') else [])
        assert sample['configured'] == expected
    index = json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256'] == r['image_sha256'] == sha(r['image'])
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    provenance = json.loads(Path(r['image']).with_name(Path(r['image']).stem+'-sources.json').read_text())
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    result = dict(status='PASS', cases=9, report_sha256=sha(path), image_sha256=r['image_sha256'],
                  production_sources=len(provenance['files']), production_fix=False, new_build=False,
                  hardware_testing=False, full_ota_install=False, scope=__doc__,
                  decision='Original mandatory child failures block FinishUpdate/slot, optional exit failure follows original policy, cancellation reaps child without completion/slot. No production change justified.',
                  limits=['explicit QEMU exec bridge', 'mount and readonly effects are fixtures',
                          'boot/hardware effects are fixtures', 'harmless program, no original otapreopt execution',
                          'no actual SnapshotManager, payload, namespace or complete OTA integration'])
    (ROOT/'logs/ota-postinstall-program-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: nine actual ARM64 program/parent lifecycle cases, six stock manifest configurations;',
          len(provenance['files']), 'unchanged production sources; no build')


if __name__ == '__main__':
    main()
