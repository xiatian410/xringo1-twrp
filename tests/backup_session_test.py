#!/usr/bin/env python3
"""Execute production backup manager, tar fork/pipe/child lifecycle and .info save.

Uses real host processes, signals, pipes and files in private fixtures. Archive
encoding, partition mounts, GUI and digest generation are boundary substitutes;
this does not test compression/encryption codecs, block devices or Android init.
"""
import argparse, hashlib, json, subprocess, tempfile, re, os, signal, ctypes, time
from pathlib import Path
def method(text, signature):
 start=text.index(signature)
 tokens=re.compile(r'''/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' ''',re.S | re.X)
 masked=tokens.sub(lambda m:' '*len(m[0]),text)
 opening=masked.index('{',start);end=opening+1;depth=1
 while depth:
  depth+=(masked[end]=='{')-(masked[end]=='}');end+=1
 return text[start:end]
ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/root/AAA/twrp/bootable/recovery')
CASES=['session-final-size-fail','session-normal','session-after-cancel','session-early-cancel','session-unknown-first',
 'session-unknown-last','session-empty','session-duplicates','session-parent-child',
 'session-absent-child','session-absent-selected','session-disabled','session-mount-fail',
 'session-size-fail','session-overflow','session-low-space','session-existing','session-symlink',
 'session-name-dot','session-name-parent','session-fail-first','session-fail-last',
 'session-cancel-first','session-cancel-last','session-digest-fail','session-digest-cancel',
 'session-cancel-finish','session-folder-replaced','session-no-delimiter','session-encrypted-external',
 'tar-normal','tar-child-fail','tar-list-fail','tar-fork-fail','tar-pre-cancel',
 'tar-info-create-fail','tar-info-sync-fail','tar-cancel','tar-repeat-cancel','tar-group-cancel',
 'tar-crash-helper','tar-after-reap','tar-second-session','tar-fragmented','tar-truncated',
 'tar-wait-eintr','tar-cancel-mutable-name','tar-no-info-before-exit','tar-signal-exit',
 'gui-normal','gui-early-cancel','gui-late-cancel','gui-destroy','gui-restart','gui-double-start','gui-acknowledge']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,default=SRC)
 ap.add_argument('--report',type=Path,default=ROOT/'logs/backup-session.json');ap.add_argument('--cases',nargs='*',choices=CASES);args=ap.parse_args()
 pm=(args.source/'partitionmanager.cpp').read_text();tar=(args.source/'twrpTar.cpp').read_text()
 modern='BackupProcess*' in tar
 code='\n'.join(method(pm,s) for s in ['bool TWPartitionManager::IsBackupNameValid(',
  'bool TWPartitionManager::BackupPartition(', 'void TWPartitionManager::CleanBackupFolder(',
  'int TWPartitionManager::CheckBackupCancel(', 'int TWPartitionManager::CancelBackup(',
  'bool TWPartitionManager::RunBackup('])
 if 'readDirectory(DIR*' in tar:
  code+='\n'+method(tar,'struct dirent* readDirectory(')+'\n'+method(tar,'int closeDirectory(')
 code+='\n'+method(tar,'int twrpTar::createTarFork(')
 code+='\n'+method((SRC/'digest/twrp_digest_driver.cpp').read_text(),'std::optional<std::vector<std::string>> TwrpDigestDriver::GetBackupFiles(')
 gui=(args.source/'gui2/backend/twrp_backup_backend.cpp').read_text()
 gui_code='namespace gui2_backend {\n'+'\n'.join(method(gui,s) for s in [
  'twrp_backup_backend::~twrp_backup_backend()', 'void twrp_backup_backend::join_finished_thread(',
  'bool twrp_backup_backend::start(', 'void twrp_backup_backend::run(',
  'void twrp_backup_backend::cancel(', 'backup_status twrp_backup_backend::status(',
  'void twrp_backup_backend::acknowledge('])+'\n}'
 code+='\n'+method((SRC/'infomanager.cpp').read_text(),'int InfoManager::SaveValues(')
 with tempfile.TemporaryDirectory(prefix='dijun-backup-session-',dir='/tmp') as tmp:
  tmp=Path(tmp);h=(ROOT/'tests/backup_session_test.cpp').read_text().replace('// PRODUCTION_METHODS',code).replace('// GUI_METHODS',gui_code)
  h=h.replace('// CHILD_TYPE', 'using Child=BackupProcess;' if modern else 'using Child=pid_t;')
  h=h.replace('// RUN_BACKUP_DECL', 'bool RunBackup(bool reset_cancel=true);' if modern else 'bool RunBackup();')
  h=h.replace('// CHILD_MEMBER','BackupProcess backup_process_;' if modern else 'pid_t tar_fork_pid=0;')
  h=h.replace('// RUN_BACKUP_CALL','PartitionManager.RunBackup(scenario!="session-early-cancel")' if modern else 'PartitionManager.RunBackup()')
  h=h.replace('// CHILD_ARGUMENT','&PartitionManager.backup_process_' if modern else '&PartitionManager.tar_fork_pid')
  if modern:h='#include "backup_process.hpp"\n'+h
  (tmp/'test.cpp').write_text(h)
  cmd=['g++','-std=c++23','-O1','-g','-pthread','-Wall','-Wextra','-Wno-unused-parameter',
   '-Wno-missing-field-initializers','-fsanitize=address,undefined','-fno-sanitize-recover=all','-no-pie',
   '-I'+str(SRC),'-I/root/AAA/twrp/system/libbase/include',str(tmp/'test.cpp'),'-o',str(tmp/'test'),
   *['-Wl,--wrap='+f for f in ['fork','kill','waitpid','waitid','mkstemp','fsync','sync']]]
  subprocess.run(cmd,check=True);results=[]
  assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0  # adopt fixture orphans for cleanup
  for case in args.cases or CASES:
   wd=tmp/case;wd.mkdir();(wd/'.fixture').touch()
   with (wd/'output.log').open('w') as log:
    proc=subprocess.Popen([str(tmp/'test'),case],cwd=wd,stdout=log,stderr=log,start_new_session=True)
    try:code=proc.wait(timeout=3)
    except subprocess.TimeoutExpired:code=124
    # Negative controls may deliberately leave a hung child/helper. Use pidfds
    # and verify its actual cwd is this private fixture before signalling it.
    for entry in Path('/proc').iterdir():
     if not entry.name.isdigit():continue
     fd=None
     try:
      fd=os.pidfd_open(int(entry.name))
      if (entry/'cwd').resolve(strict=True)==wd:signal.pidfd_send_signal(fd,signal.SIGKILL)
     except (OSError,ProcessLookupError):pass
     finally:
      if fd is not None:os.close(fd)
    proc.wait(timeout=2)
    until=time.monotonic()+1
    while time.monotonic()<until:
     try:
      child,_=os.waitpid(-1,os.WNOHANG)
      if child==0:time.sleep(.005)
     except ChildProcessError:break
   r=subprocess.CompletedProcess([],code,(wd/'output.log').read_text(),'')
   result=dict(case=case,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,output=r.stdout+r.stderr)
   results.append(result);print(result['status'],case,flush=True)
  sources=[args.source/f for f in ['partitionmanager.cpp','twrpTar.cpp','gui2/backend/twrp_backup_backend.cpp']]
  if modern:sources.append(SRC/'backup_process.hpp')
  shared=[SRC/f for f in ['infomanager.cpp','variables.h','twrp_operation_executor.h','gui2/backend/twrp_backup_backend.h','gui2/backend/backup_backend.h','backup_manifest.hpp','digest/twrp_digest_driver.cpp']]
  shared+=list(Path('/root/AAA/twrp/system/libbase/include/android-base').glob('*.h'))
  report=dict(status='PASS' if all(x['status']=='PASS' for x in results) else 'FAIL',scope=__doc__.strip(),
   sources={str(p):sha(p) for p in sources},shared_sources={str(p):sha(p) for p in shared},
   test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/backup_session_test.cpp',ROOT/'tests/restore_session_test.py']},
   cases=results,compile_command=cmd,
   boundaries=['Archive byte stream and digest generation are substitutes, not codec or cryptographic verification.',
    'Actual InfoManager::SaveValues and real directory/file operations; mount/provider/UI boundaries substituted.',
    'Child process groups execute only within this harness; signal wrapper refuses unowned IDs and records invalid calls.',
    'Cancellation cannot interrupt kernel uninterruptible I/O; no power-loss or Android child-reaper simulation.'])
  args.report.write_text(json.dumps(report,indent=2)+'\n')
 return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
