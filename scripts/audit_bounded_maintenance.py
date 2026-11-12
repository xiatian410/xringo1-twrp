#!/usr/bin/env python3
"""Bind this finite six-group maintenance batch; no full hardware/OTA acceptance."""
import hashlib,json
from pathlib import Path
from sync_device_tree import ROOT,TREE,ANDROID,manifest
from firmware_facts import boot_parts,ramdisk_entries

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bindings(report,keys=('sources','test_sources')):
 for key in keys:
  for path,digest in report.get(key,{}).items():
   path=Path(path) if path.startswith('/') else ROOT/path
   assert sha(path)==digest,str(path)
def main():
 index=json.loads((ROOT/'simulation-report.json').read_text());image=Path(index['image'])
 assert image.name=='recovery-dijun-unified-bounded-maintenance.img'
 assert sha(image)==index['image_sha256']=='218c5edd28c4e458464fc035a73b68808b016598c51e50877b2c0a1b055da3c3'
 source=json.loads(image.with_name(image.stem+'-sources.json').read_text());assert source['jobs']==30 and len(source['files'])==775
 for p,digest in source['files'].items():assert sha(p)==digest,p
 assert sha(image)==source['image_sha256'] and sha(ROOT/source['build_log'])==source['build_log_sha256']
 text=(ROOT/source['build_log']).read_text();assert 'Deleted images and staging directories' in text and text.count('build completed successfully')==2
 assert '//system/update_engine:update_engine_sideload clang++ aosp/sideload_main.cc' in text
 assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/bounded-final-source.log').read_text()
 checks=[]
 for name,count,oldfail in [('temperature-camera',11,10),('resize-capacity',16,7),('sideload-rejection',7,4)]:
  for old in [False,True]:
   path=ROOT/'logs'/(name+('-before' if old else '')+'.json');r=json.loads(path.read_text());bindings(r)
   assert len(r['cases'])==count and r['status']==('FAIL' if old else 'PASS')
   failures=sum(c.get('status')=='FAIL' or c.get('returncode',0)!=0 for c in r['cases']);assert failures==(oldfail if old else 0)
   checks.append(dict(name=path.stem,count=count,failures=failures,status=r['status'],sha256=sha(path)))
 for name,count in [('refresh-page-lifecycle',3),('bounded-status-readings',28),('bounded-init',5)]:
  path=ROOT/'logs'/(name+'.json');r=json.loads(path.read_text());bindings(r);assert r['status']=='PASS'
  assert len(r['checks'] if name=='bounded-init' else r['cases'])==count
  checks.append(dict(name=name,count=count,status='PASS',sha256=sha(path)))
 r=json.loads((ROOT/'logs/bounded-profile-runtime.json').read_text());bindings(r)
 assert r['status']=='PASS' and r['tests_run']==9 and len(r['cases'])==102 and r['image_sha256']==sha(image)
 r=json.loads((ROOT/'logs/bounded-repair-status.json').read_text());bindings(r);assert r['status']=='PASS' and 'assertions=146 failures=0' in r['output']
 reused=[]
 for name,count in [('rtc-driver-emulation',56),('video-failure',6),('video-timeline',3)]:
  path=ROOT/'logs'/(name+'.json');r=json.loads(path.read_text());bindings(r);assert r['status']=='PASS' and len(r['cases'])==count
  reused.append(dict(name=name,count=count,sha256=sha(path),reason='All relevant bound sources unchanged; no rerun or new hardware claim.'))
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 engine=ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/update_engine_sideload'
 assert entries['system/bin/update_engine_sideload']==engine.read_bytes()
 assert b'ro.twrp.device_label=XRING O1\n' in entries['prop.default']
 assert entries['system/etc/twrp.flags']==(TREE/'profiles/common/root/system/etc/twrp.flags').read_bytes()
 package=json.loads(image.with_suffix('.json').read_text());assert package['sha256']==sha(image) and len(package['profiles'])==6
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 result=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=sha(image),production_sources=775,selected_groups=[6,7,8,10,11,12],checks=checks,reused=reused,hardware_testing=False,full_ota_payload=False,refresh_incident_fixed=False)
 (ROOT/'logs/bounded-maintenance-delivery.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: finite maintenance/build/provenance; remaining hardware/OTA/presentation limits preserved')
if __name__=='__main__':main()
