#!/usr/bin/env python3
"""Review stock OS4 otapreopt recovery guard; reject unnecessary ART service adaptation."""
import hashlib
import json
from pathlib import Path
from sync_device_tree import ROOT, TREE, ANDROID, manifest
from firmware_facts import boot_parts, ramdisk_entries


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = ROOT/'logs/ota-stock-postinstall.json'
    r = json.loads(path.read_text())
    assert r['status'] == 'PASS' and len(r['cases']) == 8
    assert r['exact_stock_script'] and r['actual_arm64_shell']
    assert r['actual_getprop_missing_property_area'] and not r['art_executed']
    assert r['actual_getprop_probe']['returncode'] == 0
    assert r['actual_getprop_probe']['stdout'].strip() == ''
    for group in ['sources', 'dependencies']:
        for name, digest in r[group].items():
            assert sha(name) == digest, name
    assert [s['sample'] for s in r['samples']] == ['os4-current','os4-stable']
    assert len({s['script_sha256'] for s in r['samples']}) == 1
    assert all(s['script_size'] == 4461 for s in r['samples'])
    for case in r['cases']:
        assert all(case['checks'].values())
        assert case['returncode'] == (1 if case['name'] == 'boot-complete-invalid-slot' else 0)
    index = json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256'] == r['image_sha256'] == sha(r['image'])
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    provenance = json.loads(Path(r['image']).with_name(Path(r['image']).stem+'-sources.json').read_text())
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    entries = {e[0]:e[-1] for e in ramdisk_entries(boot_parts(Path(r['image']).read_bytes())[1]['ramdisk'])}
    for name, digest in r['image_entries'].items():
        assert hashlib.sha256(entries[name]).hexdigest() == digest
    result = dict(status='PASS', scope=__doc__, report_sha256=sha(path),cases=8,
        production_sources=len(provenance['files']),image_sha256=r['image_sha256'],production_fix=False,
        new_build=False,full_ota_install=False,hardware_testing=False,
        decision='Preserve stock bootcomplete guard. Actual delivered ARM64 shell/toolbox executes stock scripts and exits before ART when bootcomplete is absent/not1. Do not add ART service or rewrite script based solely on Recovery missing framework.',
        limits=['actual Android property area untested', 'native exec adapters explicit',
                'no mount/namespace/SELinux integration', 'no ART/dexopt or full OTA execution'])
    (ROOT/'logs/ota-stock-postinstall-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: exact two-stock-script recovery guard, eight cases, actual delivered shell/getprop;',
          len(provenance['files']),'unchanged production sources')


if __name__ == '__main__':
    main()
