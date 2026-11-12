#!/usr/bin/env python3
"""Join original Recovery user control and vold CE cache/lock/unlock methods.

Actual methods: DecryptDevice, MarkUserDecrypted, CheckUsersDecryptionStatus,
MarkDataLocked, Decrypt_CE_storage, fscrypt_unlock/lock_ce_storage and
evict_user_keys. Key derivation/Gatekeeper/TEE, key reads/install/evict ioctls,
filesystem preparation, properties and mounts are explicit fixtures. No phone,
real keys, fscrypt kernel, parent-bound profile protocol or actual remount.
"""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
from nested_partition_path_test import method
ROOT=Path(__file__).resolve().parents[1];REC=Path('/root/AAA/twrp/bootable/recovery');VOLD=REC.parents[1]/'system/vold'
CASES=['success-owner','success-secondary','wrong-secret','install-failed','prepare-failed-owner','prepare-failed-secondary','eviction-failure','cached-policy','unmount-reunlock','adoptable-eviction','unmount-eviction-failure','already-unlocked','missing-user','DE-failed','service-not-ready']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,default=REC/'partitionmanager.cpp');ap.add_argument('--report',type=Path,default=ROOT/'logs/ce-lifecycle.json');a=ap.parse_args()
 fs=VOLD/'FsCrypt.cpp';decrypt=VOLD/'Decrypt.cpp';text=a.source.read_text()
 r='\n'.join(method(text,s) for s in ['int TWPartitionManager::DecryptDevice(','void TWPartitionManager::MarkUserDecrypted(','void TWPartitionManager::CheckUsersDecryptionStatus(','void TWPartitionManager::MarkDataLocked('])
 v='\n'.join(method(fs.read_text(),s) for s in ['static bool evict_user_keys(','bool fscrypt_unlock_ce_storage(','bool fscrypt_lock_ce_storage('])
 ce=method(decrypt.read_text(),'bool Decrypt_CE_storage(')
 harness=(ROOT/'tests/ce_lifecycle_test.cpp').read_text().replace('// VOLD_METHODS',v).replace('// DECRYPT_CE_METHOD',ce).replace('// RECOVERY_METHODS',r)
 cases=[]
 with tempfile.TemporaryDirectory(prefix='ce-lifecycle-') as tmp:
  temp=Path(tmp);(temp/'test.cpp').write_text(harness)
  subprocess.run(['g++','-std=c++23','-O1','-g','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie',str(temp/'test.cpp'),'-o',str(temp/'test')],check=True)
  for name in CASES:
   run=subprocess.run([str(temp/'test'),name],capture_output=True,text=True,timeout=10)
   cases.append(dict(case=name,status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,output=run.stdout+run.stderr));print(name,cases[-1]['status'],flush=True)
 sources=[a.source,fs,decrypt,VOLD/'Android.bp',REC/'Android.bp',Path(__file__).resolve(),ROOT/'tests/ce_lifecycle_test.cpp',ROOT/'tests/nested_partition_path_test.py']
 report=dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):sha(p) for p in sources},vold_commit=subprocess.check_output(['git','-C',str(VOLD),'rev-parse','HEAD'],text=True).strip())
 a.report.write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
