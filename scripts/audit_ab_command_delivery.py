#!/usr/bin/env python3
"""Bind A/B command failure handling to the clean image; not OTA application proof."""
import hashlib,json
from pathlib import Path
from sync_device_tree import ROOT,TREE,ANDROID,manifest
from firmware_facts import boot_parts,ramdisk_entries

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 index=json.loads((ROOT/'simulation-report.json').read_text());image=Path(index['image']);assert image.name=='recovery-dijun-unified-ab-command.img'
 assert sha(image)==index['image_sha256']
 source=json.loads(image.with_name(image.stem+'-sources.json').read_text());assert source['image_sha256']==sha(image) and source['jobs']==30
 for p,digest in source['files'].items():assert sha(p)==digest,p
 build=ROOT/source['build_log'];assert sha(build)==source['build_log_sha256'];text=build.read_text();assert text.count('build completed successfully')==2 and 'Deleted images and staging directories' in text
 assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/ab-command-final-source.log').read_text()
 evidence=[]
 for name,count,status in [('ab-command-chain',21,'PASS'),('ab-command-before',21,'FAIL'),('ab-command-zip-regression',36,'PASS')]:
  path=ROOT/'logs'/(name+'.json');r=json.loads(path.read_text());assert len(r['cases'])==count and r['status']==status
  for p,digest in r['sources'].items():assert sha(p)==digest,p
  if name=='ab-command-before':assert sum(c['status']=='FAIL' for c in r['cases'])==8
  if name=='ab-command-chain':assert all(c['engine_entered']==c['expected_engine'] for c in r['cases'])
  assert any(c.get('evidence')=='logs/'+name+'.json' and c['evidence_sha256']==sha(path) for c in index['additional_checks'])
  evidence.append(dict(name=name,count=count,status=status,sha256=sha(path)))
 _,parts=boot_parts(image.read_bytes());entries={e[0]:e[-1] for e in ramdisk_entries(parts['ramdisk'])}
 assert b'ro.twrp.device_label=XRING O1\n' in entries['prop.default']
 assert entries['system/etc/twrp.flags']==(TREE/'profiles/common/root/system/etc/twrp.flags').read_bytes()
 package=json.loads(image.with_suffix('.json').read_text());assert package['sha256']==sha(image) and len(package['profiles'])==6
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 result=dict(status='PASS',image=str(image),image_sha256=sha(image),production_sources=len(source['files']),checks=evidence,scope=__doc__,hardware_testing=False)
 (ROOT/'logs/ab-command-delivery.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: clean build, source/ZIP evidence bindings, inherited labels/flags; no OTA application or device test')
if __name__=='__main__':main()
