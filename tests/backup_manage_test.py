#!/usr/bin/env python3
"""Execute production tool worker backup rename/delete against private files.

Real threads, shell on old implementation, renameat2 and filesystem removal;
DataManager and operation presentation are explicit boundaries. No GUI or device.
"""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path
from nested_partition_path_test import ROOT, SRC, method

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=SRC/'gui2/backend/twrp_tools_backend.cpp');p.add_argument('--report',type=Path,default=ROOT/'logs/backup-manage.json');a=p.parse_args()
 s=a.source.read_text(); signatures=['twrp_tools_backend::~twrp_tools_backend()', 'void twrp_tools_backend::join_finished_thread()', 'bool twrp_tools_backend::start(', 'void twrp_tools_backend::run(', 'tool_state twrp_tools_backend::status()', 'void twrp_tools_backend::acknowledge()']
 # Keep helper definitions in production order, including all fd cleanup logic.
 helpers=s[s.index('// Backup folder operations'):s.index('// GUIAction::cmd')] if '// Backup folder operations' in s else ''
 with tempfile.TemporaryDirectory(prefix='backup-manage-') as tmp:
  w=Path(tmp);(w/'remove.inc').write_text(method((SRC/'twrp_functions.cpp').read_text(),'int TWFunc::RemoveDir('));(w/'worker.inc').write_text((method(s,'std::string base_name(')+'\n' if 'std::string base_name(' in s else '')+helpers+'\n'+'\n\n'.join(method(s,x) for x in signatures));binary=w/'test'
  command=['g++','-std=c++20','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=undefined','-I'+str(w),'-I'+str(SRC/'gui2'),'-I'+str(SRC),str(ROOT/'tests/backup_manage_test.cpp'),str(SRC/'twrp_operation_executor.cpp'),'-lpthread','-o',str(binary)]
  subprocess.run(command,check=True);cases=[]
  for name in ['rename','special-source','special-root','different-parent','existing-target','invalid-name','symlink-source','delete-special','delete-outside','delete-symlink','missing-source','reused-worker']:
   folder=w/name;folder.mkdir();r=subprocess.run([str(binary),name,str(folder)],capture_output=True,text=True,timeout=15);cases.append(dict(name=name,status='PASS' if r.returncode==0 else 'FAIL',stdout=r.stdout,stderr=r.stderr));print(name,cases[-1]['status'],flush=True)
 sources=[a.source,Path(__file__),ROOT/'tests/backup_manage_test.cpp',SRC/'twrp_operation_executor.cpp',SRC/'twrp_operation_executor.h',SRC/'gui2/backend/twrp_tools_backend.h',SRC/'gui2/backend/tools_backend.h',SRC/'twrp_functions.cpp',ROOT/'tests/nested_partition_path_test.py']
 report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,compile_command=command,sources={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources})
 a.report.write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
