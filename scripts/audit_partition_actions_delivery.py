#!/usr/bin/env python3
"""Bind the partition UI fix to a clean image and focused offline regression."""
import hashlib,json
from pathlib import Path
from sync_device_tree import ROOT,TREE,ANDROID,manifest
from firmware_facts import boot_parts,ramdisk_entries

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 index=json.loads((ROOT/'simulation-report.json').read_text());image=Path(index['image'])
 assert image.name=='recovery-dijun-unified-partition-actions.img'
 assert sha(image)==index['image_sha256']
 sources=json.loads(image.with_name(image.stem+'-sources.json').read_text())
 assert sources['image_sha256']==sha(image) and sources['jobs']==30
 for name,digest in sources['files'].items():assert sha(name)==digest,name
 assert len(sources['files'])==769
 build=ROOT/sources['build_log'];assert sha(build)==sources['build_log_sha256']
 text=build.read_text();assert text.count('build completed successfully')==2 and 'Deleted images and staging directories' in text
 assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/partition-actions-final-source.log').read_text()
 _,parts=boot_parts(image.read_bytes());entries={x[0]:x[-1] for x in ramdisk_entries(parts['ramdisk'])}
 flags=TREE/'profiles/common/root/system/etc/twrp.flags'
 assert entries['system/etc/twrp.flags']==flags.read_bytes()
 checks=[]
 for name,count,status in [('nv-partition-actions',26,'PASS'),('nv-partition-actions-before',26,'FAIL'),('install-target-interaction',25,'PASS'),('partition-actions-image-chain',40,'PASS'),('partition-actions-repair-chain',7,'PASS'),('partition-actions-mount',26,'PASS')]:
  path=ROOT/'logs'/(name+'.json');r=json.loads(path.read_text())
  assert r['status']==status and len(r['cases'])==count
  for source,digest in r['sources'].items():assert sha(source)==digest,source
  if name=='install-target-interaction':assert r['image_sha256']==sha(image) and len(r['parser_rows'])==5
  if name.endswith('-before'):assert sum(c['status']=='FAIL' for c in r['cases'])==19
  assert any(c.get('evidence')=='logs/'+name+'.json' and c['evidence_sha256']==sha(path) for c in index['additional_checks'])
  checks.append(dict(name=name,count=count,status=status,sha256=sha(path)))
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 package=json.loads(image.with_suffix('.json').read_text());assert package['sha256']==sha(image) and len(package['profiles'])==6
 result=dict(status='PASS',image=str(image),image_sha256=sha(image),production_sources=len(sources['files']),checks=checks,scope=__doc__,hardware_testing=False)
 (ROOT/'logs/partition-actions-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS: clean image, 769 sources, flags packaged, focused GUI/operation checks; hardware unverified')
if __name__=='__main__':main()
