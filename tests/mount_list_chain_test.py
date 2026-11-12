#!/usr/bin/env python3
"""Production mount/storage list branches, snapshots, backend and LVGL builders.

Partition classification and presence are fixtures derived from the shipped
fstab inventory, not executed fstab parsing or real block discovery. Only mount
and storage branches of GetPartitionList are compiled; unrelated branches are
omitted. No mounting, GUI pointer dispatch, actual storage or phone is accessed.
"""
import json
import argparse
import re
import subprocess
import tempfile
from pathlib import Path
from haptics_ui_test import ROOT,SRC,LVGL,lvgl_library,sha
from nested_partition_path_test import method

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=ROOT/'logs/mount-list-chain.json')
    args=parser.parse_args()
    inventory_path=ROOT/'logs/shipped-mount-inventory.json'
    inventory=json.loads(inventory_path.read_text())
    index=json.loads((ROOT/'simulation-report.json').read_text())
    assert inventory['image_sha256']==index['image_sha256']==sha(Path(index['image']))
    core=SRC.parent;pm=core/'partitionmanager.cpp';backend=SRC/'backend/twrp_mount_backend.cpp'
    library,provenance=lvgl_library()
    production=['pages/mount_page.cpp','pages/select_storage_page.cpp','components/check_row.cpp',
                'components/setting_card.cpp','components/section_label.cpp','components/icon.cpp',
                'core/ui_helpers.cpp','core/ui_metrics.cpp','core/ui_event_guard.cpp',
                'gui2_svg_cache.cpp','i18n/en.cpp']
    sources=[SRC/p for p in production]
    with tempfile.TemporaryDirectory(prefix='mount-list-chain-') as tmp:
        temp=Path(tmp)
        text=pm.read_text()
        lists=method(text,'void TWPartitionManager::GetPartitionList(')
        # Preserve the two target branches byte-for-byte; exclude unrelated dependencies.
        lists=lists[:lists.index('  } else if (list_type == "backup")')]+ '  }\n}\n'
        methods=[lists,method(text,'bool TWPartitionManager::TryGetPartitionList('),
                 method(text,'void TWPartitionManager::RefreshPartitionListSnapshots(')]
        (temp/'partition-methods.inc').write_text('\n\n'.join(methods))
        header=core/'partitions.hpp'
        (temp/'partition-list.inc').write_text(re.search(r'struct PartitionList \{.*?\n\};',header.read_text(),re.S)[0])
        text=backend.read_text()
        methods=[method(text,sig) for sig in ['static std::string otg_name(',
            'static void sort_otg_partitions(', 'std::vector<mount_target> twrp_mount_backend::targets(',
            'std::vector<storage_device> twrp_mount_backend::storages(']]
        (temp/'backend-methods.inc').write_text('\n\n'.join(methods))
        fixtures=[]
        for group in inventory['groups']:
            if group['removable_template']:continue
            path=group['mount_point'];name=path.lstrip('/')
            fixtures.append(dict(path=path,name=name,raw=group['raw_image']))
        code=[]
        for f in fixtures:
            p,n=json.dumps(f['path']),json.dumps(f['name'])
            code.append('{ TWPartition p; p.mount_point_='+p+'; p.display_name_='+n+'; p.can_be_mounted_='+str(not f['raw']).lower()+';')
            if f['path']=='/data':code.append('p.is_storage_=true;p.storage_name_="Internal Storage";p.storage_path_="/data/media";')
            code.append('parts.push_back(p); }')
        for path in ['/usbotg-1-2','/usbotg-1-10']:
            p=json.dumps(path)
            code.append('{ TWPartition p;p.mount_point_=p.storage_path_='+p+';p.display_name_=p.storage_name_="Storage";p.is_storage_=true;parts.push_back(p); }')
        (temp/'fixture.inc').write_text('\n'.join(code))
        artwork=SRC/'image/ic_arrow_right.svg'
        (temp/'gui2_svg_assets.h').write_bytes(subprocess.check_output(['python3',str(SRC/'generate_svg_header.py'),str(artwork)]))
        command=['g++','-std=c++23','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all',
                 '-DLV_CONF_INCLUDE_SIMPLE','-DLV_LVGL_H_INCLUDE_SIMPLE','-DTW_FRAMERATE=120',
                 '-I'+str(temp),'-I'+str(SRC),'-I'+str(LVGL),str(ROOT/'tests/mount_list_chain_test.cpp'),
                 *map(str,sources),str(library),'-lpthread','-lm','-o',str(temp/'test')]
        subprocess.run(command,check=True)
        cases=[]
        for name in ['normal','absent-nv','duplicate-input-names','data-absent','remove-readd','shipped-otg-paths']:
            run=subprocess.run([str(temp/'test'),name],capture_output=True,text=True,timeout=30)
            cases.append(dict(case=name,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr))
            print(name,'PASS' if run.returncode==0 else 'FAIL',run.stdout+run.stderr,flush=True)
    files=sources+[pm,backend,header,Path(__file__).resolve(),ROOT/'tests/mount_list_chain_test.cpp',
                   ROOT/'tests/haptics_ui_test.py',ROOT/'tests/nested_partition_path_test.py',
                   inventory_path,ROOT/'scripts/inspect_mount_inventory.py',artwork,SRC/'generate_svg_header.py']
    files+=sorted(SRC.rglob('*.h'))
    report=dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',
                scope=__doc__,image_sha256=index['image_sha256'],cases=cases,
                fixture_partitions=fixtures,sources={str(p):sha(p) for p in files},lvgl=provenance)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__': raise SystemExit(main())
