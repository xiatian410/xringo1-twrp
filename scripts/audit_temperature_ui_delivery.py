#!/usr/bin/env python3
"""Bind temperature GUI source, actual LVGL checks, clean image and same-image profile replay."""
import hashlib,json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(n):return json.loads((ROOT/n).read_text())
def main():
 index=load('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert image.name=='recovery-dijun-unified-temperature-ui.img' and digest==index['image_sha256']
 reports=[('logs/temperature-ui.json',11),('logs/temperature-status-regression.json',28)]
 for name,count in reports:
  r=load(name);assert r['status']=='PASS' and len(r['cases'])==count and all(c['returncode']==0 for c in r['cases'])
  for group in ['sources','test_sources']:
   for n,h in r.get(group,{}).items():
    p=Path(n);p=p if p.is_absolute() else Path('/root/AAA/twrp/bootable/recovery')/n
    assert sha(p)==h,n
  c,=[c for c in index['checks'] if c['evidence']==name];assert c['evidence_sha256']==sha(ROOT/name)
 ui=load(reports[0][0]);assert len(ui['frames'])==10
 for f in ui['frames']:assert sha(ROOT/f['path'])==f['sha256']
 for n,h in ui['lvgl']['source_files'].items():assert sha(Path(n))==h,n
 src=json.loads(image.with_name(image.stem+'-sources.json').read_text());assert src['image_sha256']==digest and len(src['files'])==723 and src['jobs']==30
 assert src['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
 for n,h in src['files'].items():assert sha(Path(n))==h,n
 assert sha(ROOT/src['build_log'])==src['build_log_sha256']
 assert 'build completed successfully' in (ROOT/src['build_log']).read_text()
 meta=json.loads(image.with_suffix('.json').read_text());assert meta['sha256']==digest and len(meta['profiles'])==6
 assert 'status bar' in meta['status_build_configuration']['cpu_temperature_gui']
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for n,h in meta['binary_hashes'].items():assert hashlib.sha256(entries[n]).hexdigest()==h,n
 for text in [b'tw_cpu_temp',b'tw_no_cpu_temp','%d°C'.encode()]:assert text in entries['system/lib64/libgui2.so']
 old=load('imgs/built/recovery-dijun-unified-thermal-identity.json')
 assert old['binary_hashes']['system/lib64/libtwrpminui.so']==meta['binary_hashes']['system/lib64/libtwrpminui.so']
 runtime=load('logs/temperature-ui-profile-runtime.json');assert runtime['status']=='PASS' and runtime['tests_run']==9 and len(runtime['cases'])==102 and runtime['image_sha256']==digest
 for group in ['sources','test_sources']:
  for n,h in runtime[group].items():
   p=Path(n) if Path(n).is_absolute() else ROOT/n;assert sha(p)==h,n
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 evidence=[name for name,count in reports]+['logs/temperature-ui-profile-runtime.json','logs/verify-temperature-ui.log','logs/temperature-ui-final-source-recheck.log']
 out=dict(status='PASS',scope=__doc__,image_sha256=digest,source_files=723,gui_groups=11,status_cases=28,runtime_groups=9,runtime_calls=102,evidence={n:sha(ROOT/n) for n in evidence},documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/STATUS-ADAPTATION.md','FEATURE-USAGE.md']},audit_script_sha256=sha(Path(__file__)),verifier_sha256=sha(ROOT/'scripts/verify_unified_recovery.py'))
 (ROOT/'logs/temperature-ui-delivery.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS: GUI11/status28;723 sources;runtime9 groups/102 calls;motor/sensor hardware unverified.')
if __name__=='__main__':main()
