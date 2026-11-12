#!/usr/bin/env python3
"""Execute original GUI mount list/action methods with explicit core doubles.

No real mount, device or settings access. Confirms NV/protection rows are hidden
and stale/manual toggle calls are rejected in both directions, including a
resolved alias. Core mounting remains outside this UI policy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import ROOT,SRC,method

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--source',type=Path,default=SRC/'gui2/backend/twrp_mount_backend.cpp')
 ap.add_argument('--report',type=Path,default=ROOT/'logs/nv-mount-policy.json')
 args=ap.parse_args();text=args.source.read_text()
 bodies=[method(text,s) for s in ['static std::string otg_name(', 'static void sort_otg_partitions(',
   'std::vector<mount_target> twrp_mount_backend::targets(', 'bool twrp_mount_backend::set_mounted(']]
 blocked=['/nvram','/proinfo','/nvdata','/nvcfg','/protect_f','/protect_s',
  '/mnt/vendor/nvram','/mnt/vendor/proinfo','/mnt/vendor/nvdata','/mnt/vendor/nvcfg',
  '/mnt/vendor/protect_f','/mnt/vendor/protect_s','/mnt/vendor/nvdata/',
  '/mnt/vendor/nvdata/subdir','mnt/vendor/nvcfg','/mnt/vendor/../vendor/nvdata','/alias']
 allowed=['/data','/system','/vendor','/metadata','/cache','/mnt/vendor/persist',
  '/storage/usbotg-sdz-1','/mnt/vendor/nvdata-other','/nvdata_backup']
 cases=[]
 with tempfile.TemporaryDirectory(prefix='nv-mount-policy-') as tmp:
  work=Path(tmp);code=work/'test.cpp'
  code.write_text((ROOT/'tests/nv_mount_policy_test.cpp').read_text().replace('// METHODS','\n'.join(bodies)))
  cmd=['g++','-std=c++23','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-no-pie',
       '-I'+str(SRC/'gui2/backend'),'-I'+str(SRC.parents[1]/'system/libbase/include'),str(code),'-pthread','-o',str(work/'test')]
  subprocess.run(cmd,check=True)
  for path in blocked+allowed:
   run=subprocess.run([str(work/'test'),path,str(int(path in blocked))],capture_output=True,text=True,timeout=10)
   cases.append(dict(path=path,blocked=path in blocked,exit=run.returncode,status='PASS' if run.returncode==0 else 'FAIL',output=run.stdout+run.stderr))
   print(cases[-1]['status'],path,flush=True)
 files=[args.source,SRC/'gui2/backend/mount_backend.h',Path(__file__).resolve(),ROOT/'tests/nv_mount_policy_test.cpp',ROOT/'tests/nested_partition_path_test.py']
 report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):sha(p) for p in files},compile_command=cmd)
 args.report.write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
