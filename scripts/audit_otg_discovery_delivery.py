#!/usr/bin/env python3
"""Bind the screenshot-driven OTG discovery fix to its candidate and host checks.

Focused delivery audit, not full-goal or hardware acceptance. Original discovery
methods run with explicit filesystem/device boundaries; GUI uses actual paths.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from sync_device_tree import ROOT, TREE, ANDROID, manifest

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
def read(name):return json.loads((ROOT/name).read_text())
def bindings(mapping):
    for name,expected in mapping.items():assert sha(ROOT/name)==expected,name

def main():
    index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
    assert image.name=='recovery-dijun-unified-otg-discovery.img'
    assert digest==index['image_sha256']
    provenance=read(image.with_name(image.stem+'-sources.json'))
    assert provenance['image_sha256']==digest and provenance['jobs']==30
    assert len(provenance['files'])==741
    bindings(provenance['files'])
    for name,target in provenance['symlinks'].items():assert os.readlink(name)==target,name
    assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
    log=ROOT/provenance['build_log'];assert sha(log)==provenance['build_log_sha256']
    text=log.read_text();assert text.count('build completed successfully')>=2 and 'Deleted images and staging directories' in text
    # The old image and its provenance were removed from the workspace after
    # the build. Compare maintained source specifications and preserved files,
    # without claiming that the old image bytes have been read again.
    prior_tree=ROOT/'backups/device-tree-1794468206009489602'
    prior_series=read(prior_tree/'patches/series.json')
    series=read(TREE/'patches/series.json')
    delta=set()
    for repo,spec in prior_series['repositories'].items():
        current_spec=series['repositories'][repo]
        assert current_spec['commit']==spec['commit']
        assert not set(spec['result_files'])-set(current_spec['result_files'])
        for name,value in current_spec['result_files'].items():
            if spec['result_files'].get(name)!=value:delta.add(repo+'/'+name)
    assert delta=={'bootable/recovery/'+name for name in ['partitionmanager.cpp','gui2/backend/mount_backend.h','sysfs_device_match.hpp']}
    old_tree=manifest(prior_tree);new_tree=manifest(TREE)
    assert not set(old_tree)-set(new_tree)
    assert {n for n,v in new_tree.items() if old_tree.get(n)!=v}=={'patches/series.json','patches/0048-otg-controller-discovery.patch'}
    prior_files={'partitionmanager.cpp':'partitionmanager.cpp','gui2/backend/mount_backend.h':'mount_backend.h'}
    for name,saved in prior_files.items():
        spec=prior_series['repositories']['bootable/recovery']
        expected=spec['result_files'].get(name)
        if expected is None:
            baseline=subprocess.check_output(['git','-C',str(ANDROID/'bootable/recovery'),'show',spec['commit']+':'+name])
            expected=hashlib.sha256(baseline).hexdigest()
        assert sha(ROOT/'logs/otg-discovery-before'/saved)==expected,name
    metadata=read(image.with_suffix('.json'));assert metadata['sha256']==digest and len(metadata['profiles'])==6
    evidence=['logs/otg-discovery.json','logs/otg-discovery-before.json','logs/mount-list-chain.json',
              'logs/otg-discovery-settings-joined.json','logs/otg-discovery-selection.json',
              'logs/otg-discovery-profile-runtime.json','logs/otg-discovery-module-state.json']
    reports={name:read(name) for name in evidence}
    for name,report in reports.items():
        for group in ['sources','shared_sources','test_sources','tests']:
            bindings(report.get(group,{}))
        if 'lvgl' in report:bindings(report['lvgl']['source_files'])
        if name!='logs/otg-discovery-before.json':assert report['status']=='PASS',name
    current=reports[evidence[0]];previous=reports[evidence[1]]
    assert len(current['cases'])==len(previous['cases'])==12
    assert all(c['returncode']==0 for c in current['cases'])
    failures={c['case'] for c in previous['cases'] if c['returncode']!=0}
    assert failures=={'hotplug-ufs','coldboot','resync-ufs','resync-mixed','pending-nodes','literal-boundary','names','ufs-with-usb-name'}
    assert all(c['returncode']==-6 and 'Assertion' in c['stderr'] for c in previous['cases'] if c['case'] in failures)
    assert current['sources'][str(ROOT/'tests/otg_discovery_test.cpp')]==previous['sources'][str(ROOT/'tests/otg_discovery_test.cpp')]
    mount=reports[evidence[2]];assert len(mount['cases'])==6 and mount['image_sha256']==digest
    assert all(c['returncode']==0 for c in mount['cases'])
    actual,=[c for c in mount['cases'] if c['case']=='shipped-otg-paths']
    for token in ['MOUNT /storage/usbotg-sdz-2\tOTG sdz 2','MOUNT /storage/usbotg-sdz-10\tOTG sdz 10',
                  'STORAGE /storage/usbotg-sdz-2\tOTG sdz 2','storage_rows=3 internal_labels=1']:
        assert token in actual['stdout'],token
    for name,count in [(evidence[3],22),(evidence[4],15)]:
        assert len(reports[name]['cases'])==count
    for name,groups,calls in [(evidence[5],9,102),(evidence[6],4,24)]:
        r=reports[name];assert r['image_sha256']==digest and r['tests_run']==groups and len(r['cases'])==calls
        assert all(c['actual']==c['expected'] for c in r['cases'])
    for name in evidence:
        matches=[c for c in index['checks']+index.get('additional_checks',[]) if c.get('evidence')==name]
        assert matches and all(c['evidence_sha256']==sha(ROOT/name) for c in matches),name
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','docs/MOUNT-LIST-EXPLANATION.md','simulation-report.md','simulation-report.json']
    report=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=digest,production_sources=741,
                discovery_cases=12,old_failures=8,mount_cases=6,settings_cases=22,selection_cases=15,
                profile_groups=9,module_groups=4,evidence={name:sha(ROOT/name) for name in evidence},
                documents={name:sha(ROOT/name) for name in docs},audit_source_sha256=sha(Path(__file__)),
                prior_source_comparison={'tree':str(prior_tree),'series_sha256':sha(prior_tree/'patches/series.json'),'changed_production_files':sorted(delta)},
                limitation='Prior backup-manifest image and provenance are absent. Previous image byte comparison unavailable; preserved tree specifications and saved old source files checked instead. Current candidate741 sources independently checked.')
    (ROOT/'logs/otg-discovery-delivery.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: OTG discovery12/old failures8;LVGL6/settings22/selection15;profile9/module4;741 sources. No hardware acceptance;full goal in_progress.')
if __name__=='__main__':main()
