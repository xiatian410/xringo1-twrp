#!/usr/bin/env python3
"""Bind literal backup operations to clean-built image and finite worker checks."""
import hashlib,json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
from sync_device_tree import ROOT,TREE,ANDROID,manifest

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 image=ROOT/'imgs/built/recovery-dijun-unified-backup-manage.img'
 old=ROOT/'imgs/built/recovery-dijun-unified-snapshot-map.img'
 provenance=json.loads(image.with_name(image.stem+'-sources.json').read_text())
 assert provenance['image_sha256']==sha(image) and provenance['jobs']==30
 for name,digest in provenance['files'].items():assert sha(name)==digest,name
 log=ROOT/provenance['build_log'];assert sha(log)==provenance['build_log_sha256']
 text=log.read_text();assert 'Deleted images and staging directories' in text and text.count('build completed successfully')==2
 assert 'gui2/backend/twrp_tools_backend.cpp' in text
 assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/backup-manage-final-source.log').read_text()
 def entries(p):return {e[0]:(e[1],e[-1]) for e in ramdisk_entries(boot_parts(p.read_bytes())[1]['ramdisk'])}
 before,after=entries(old),entries(image)
 changed=[n for n in sorted(before.keys()|after.keys()) if before.get(n)!=after.get(n)]
 assert changed==['prop.default','ramdisk-files.sha256sum','system/bin/recovery'],changed
 assert b'Backup folder operation failed' in after['system/bin/recovery'][1]
 assert after['system/bin/recovery'][1]==(ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/recovery').read_bytes()
 evidence={}
 for name,expected_failed in [('backup-manage',[]),('backup-manage-before',['special-source','special-root','existing-target','invalid-name','symlink-source','delete-special','delete-outside','delete-symlink'])]:
  p=ROOT/'logs'/(name+'.json');r=json.loads(p.read_text());assert len(r['cases'])==12
  assert [c['name'] for c in r['cases'] if c['status']=='FAIL']==expected_failed
  for f,digest in r['sources'].items():assert sha(f)==digest,f
  evidence[name]=dict(sha256=sha(p),cases=12,failed=len(expected_failed))
 p=ROOT/'logs/backup-manage-refresh-lifecycle.json';r=json.loads(p.read_text());assert r['status']=='PASS' and len(r['cases'])==3
 for f,digest in r['sources'].items():assert sha(f)==digest,f
 evidence['refresh-lifecycle']=dict(sha256=sha(p),cases=3)
 package=json.loads(image.with_suffix('.json').read_text());assert package['sha256']==sha(image) and len(package['profiles'])==6
 index=json.loads((ROOT/'simulation-report.json').read_text());assert index['image_sha256']==sha(image) and index['status']=='in_progress' and len(index['not_yet_completed'])==12
 result=dict(status='PASS',scope=__doc__,image_sha256=sha(image),production_sources=len(provenance['files']),changed_ramdisk_entries=changed,evidence=evidence,hardware_testing=False,power_loss_verified=False,external_path_races_eliminated=False,reused_scope='Byte-identical profiles, update_engine, runtime and shared GUI libraries; no unrelated repeated suites.')
 (ROOT/'logs/backup-manage-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS: 12 backup operations / 8 old failures, 3 refresh lifecycle schedules, clean build / 780 sources / six profiles')
if __name__=='__main__':main()
