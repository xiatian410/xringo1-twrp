#!/usr/bin/env python3
"""Bind settings row input regressions, maintained sources and image; no hardware acceptance."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries

ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name): return json.loads((ROOT/name).read_text())

def main():
    index=load('simulation-report.json')
    image=Path(index['image'])
    expected='3c0bed7c0e93b2b5b7a50aada62165d69562c6217955a35d85eb4e03ba7cbe67'
    assert sha(image)==index['image_sha256']==expected
    current=load('logs/settings-row.json'); before=load('logs/settings-row-before.json')
    matrix={(k,c) for k in ['check','switch'] for c in ['label','indicator','blank','double',
        'drag-out','drag-back','press-lost','scroll','disabled','rollback']}
    for report in [current,before]:
        assert len(report['cases'])==20
        assert {(c['kind'],c['case']) for c in report['cases']}==matrix
        for name,digest in {**report['sources'],**report['lvgl']['source_files']}.items():
            assert sha(Path(name))==digest,name
    assert current['status']=='PASS' and all(c['returncode']==0 for c in current['cases'])
    assert {(c['kind'],c['case']) for c in before['cases'] if c['returncode']}=={
        (k,c) for k in ['check','switch'] for c in ['label','blank','double','rollback']}
    for name in ['logs/settings-regression.json','logs/nested-partition-path-test.json']:
        report=load(name);assert report['status']=='PASS'
        for filename,digest in report['sources'].items():
            path=Path(filename) if filename.startswith('/') else Path('/root/AAA/twrp/bootable/recovery')/filename
            assert sha(path)==digest,filename
    provenance=json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256']==expected and len(provenance['files'])==716
    assert provenance['jobs']==30 and 'installclean' in provenance['build_command']
    assert '-j$(nproc)' in provenance['build_command']
    for name,digest in provenance['files'].items():assert sha(Path(name))==digest,name
    for name,target in provenance['symlinks'].items():assert str(Path(name).readlink())==target
    assert sha(ROOT/provenance['build_log'])==provenance['build_log_sha256']
    assert 'build completed successfully' in (ROOT/provenance['build_log']).read_text()
    metadata=json.loads(image.with_suffix('.json').read_text());assert metadata['sha256']==expected
    assert len(metadata['profiles'])==6
    _,parts=boot_parts(image.read_bytes());entries={e[0]:e[-1] for e in ramdisk_entries(parts['ramdisk'])}
    for name,digest in metadata['binary_hashes'].items():assert hashlib.sha256(entries[name]).hexdigest()==digest
    runtime=load('logs/settings-row-profile-runtime.json')
    assert runtime['status']=='PASS' and runtime['image_sha256']==expected
    assert runtime['tests_run']==9 and len(runtime['cases'])==102
    for name,digest in {**runtime['sources'],**runtime['test_sources']}.items():
        p=Path(name) if name.startswith('/') else ROOT/name
        assert sha(p)==digest,name
    for name in ['logs/settings-row.json','logs/settings-row-profile-runtime.json']:
        check,=[c for c in index['checks'] if c['evidence']==name]
        assert check['evidence_sha256']==sha(ROOT/name)
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','FEATURE-USAGE.md','simulation-report.md',
          'simulation-report.json','docs/SETTINGS-ADAPTATION.md']
    evidence=['logs/settings-row.json','logs/settings-row-before.json','logs/settings-regression.json',
              'logs/nested-partition-path-test.json','logs/settings-row-profile-runtime.json',
              'logs/verify-settings-row.log','logs/settings-row-final-source-recheck.log']
    result=dict(status='PASS',scope=__doc__,image_sha256=expected,sources=716,input_cases=20,
                before_failures=8,runtime_groups=9,runtime_phase_calls=102,
                evidence={n:sha(ROOT/n) for n in evidence},documentation={n:sha(ROOT/n) for n in docs},
                audit_script_sha256=sha(Path(__file__)))
    (ROOT/'logs/settings-row-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: settings whole-row input/source/image/runtime delivery; full goal incomplete')

if __name__=='__main__':main()
