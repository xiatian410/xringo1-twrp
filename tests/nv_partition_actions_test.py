#!/usr/bin/env python3
"""Execute GUI wipe/tools/image methods with counted core doubles; no devices or writes."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
from nested_partition_path_test import ROOT,SRC,method

def main():
 p=argparse.ArgumentParser();p.add_argument('--before',action='store_true');a=p.parse_args()
 source=ROOT/'logs/nv-actions-before' if a.before else SRC
 signatures={
 'twrp_wipe_backend.cpp':['bool wipe_target_allowed(', 'int wipe(', 'std::vector<wipe_target> twrp_wipe_backend::targets(', 'bool twrp_wipe_backend::start_wipe('],
 'twrp_tools_backend.cpp':['bool partition_tool_target_allowed(', 'int repair(', 'int resize(', 'int changefilesystem(', 'bool twrp_tools_backend::details(', 'bool twrp_tools_backend::start('],
 'twrp_install_backend.cpp':['std::vector<image_target> twrp_install_backend::image_targets(', 'bool twrp_install_backend::start_image(', 'void twrp_install_backend::run_image(']}
 bodies=[];bound=[]
 for name,sigs in signatures.items():
  path=source/'gui2/backend'/name;bound.append(path);text=path.read_text()
  for sig in sigs:
   if sig not in text and a.before:continue
   bodies.append(method(text,sig))
 blocked=['/nvram','/proinfo','/nvdata','/nvcfg','/protect_f','/protect_s','/mnt/vendor/nvdata','/mnt/vendor/nvcfg','/mnt/vendor/protect_f','/mnt/vendor/protect_s','/mnt/vendor/nvram','/mnt/vendor/proinfo','/mnt/vendor/../vendor/nvdata','mnt/vendor/nvcfg','/nvdata/sub','/alias']
 allowed=['/data','/cache','/boot','/metadata','/mnt/vendor/persist','/nvdata_backup','/mnt/vendor/nvdata-other']
 cases=[]
 with tempfile.TemporaryDirectory(prefix='nv-actions-') as d:
  d=Path(d);(d/'methods.inc').write_text('\n'.join(bodies))
  cmd=['g++','-std=c++23','-O1','-g','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-no-pie','-I'+str(d),'-I'+str(SRC/'gui2/backend'),str(ROOT/'tests/nv_partition_actions_test.cpp'),'-o',str(d/'test')]
  subprocess.run(cmd,check=True)
  for path in blocked+allowed+['injection','empty','stale']:
   r=subprocess.run([str(d/'test'),path,str(int(path in blocked))],capture_output=True,text=True,timeout=10)
   cases.append(dict(path=path,exit=r.returncode,status='PASS' if r.returncode==0 else 'FAIL',output=r.stdout+r.stderr))
   print(cases[-1]['status'],path,flush=True)
 bound += [SRC/'gui2/backend/mount_backend.h',Path(__file__).resolve(),ROOT/'tests/nv_partition_actions_test.cpp']
 report=dict(status='PASS' if all(c['exit']==0 for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in bound},compile_command=cmd)
 (ROOT/('logs/nv-partition-actions-before.json' if a.before else 'logs/nv-partition-actions.json')).write_text(json.dumps(report,indent=2)+'\n')
 return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
