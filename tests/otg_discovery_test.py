#!/usr/bin/env python3
"""Execute production hotplug/resync/coldboot and wildcard child discovery.

Static host executable runs inside private temporary chroots with ordinary
files and symlinks representing USB and UFS paths. stat block mode, filesystem
classification, size, mount/unmount and FindActualBlockDevice are explicit
boundaries; original FindWildcardBlockDevices is executed. No phone or real
block/mount I/O. Includes shipped fstab pattern and an 85-partition UFS fixture.
"""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path
from nested_partition_path_test import method
ROOT=Path(__file__).resolve().parents[1]
REC=Path('/root/AAA/twrp/bootable/recovery')
CASES=['hotplug-ufs','hotplug-usb','coldboot','resync-ufs','resync-mixed','pending-nodes','unpartitioned-usb','literal-boundary','names','controller-pattern','usb-with-ufs-name','ufs-with-usb-name']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--source',type=Path,default=REC/'partitionmanager.cpp')
 ap.add_argument('--header',type=Path,default=REC/'gui2/backend/mount_backend.h')
 ap.add_argument('--report',type=Path,default=ROOT/'logs/otg-discovery.json')
 a=ap.parse_args()
 fstab=ROOT/'dtsrc/O1_asic_dual/recovery/root/system/etc/recovery.fstab'
 if not fstab.exists():fstab=next((ROOT/'dtsrc/O1_asic_dual').rglob('recovery.fstab'))
 line=next(l for l in fstab.read_text().splitlines() if '/storage/usbotg' in l and not l.startswith('#'))
 pattern=line.split()[0];assert pattern=='/devices/platform/soc/*.xr_usb/*.dwc3/xhci-hcd.*.auto*'
 signatures=['void TWPartitionManager::RemoveUeventDevices(', 'void TWPartitionManager::HandleUevent(',
  'void TWPartitionManager::ResyncUeventDevices(', 'void TWPartitionManager::ProcessPendingUeventDevices(',
  'void TWPartitionManager::ResetPendingUeventDevices(', 'void TWPartitionManager::ColdbootScan(', 'void TWPartitionManager::Coldboot(']
 code='\n\n'.join(method(a.source.read_text(),s) for s in signatures)
 code+='\n'+method((REC/'partition.cpp').read_text(),'bool TWPartition::FindWildcardBlockDevices(')
 code=code.replace('stat(block.c_str()', 'fixture_stat(block.c_str()').replace('stat((path +', 'fixture_stat((path +')
 cases=[]
 with tempfile.TemporaryDirectory(prefix='otg-discovery-') as tmp:
  temp=Path(tmp);(temp/'methods.inc').write_text(code);(temp/'mount_backend.h').write_bytes(a.header.read_bytes())
  subprocess.run(['g++','-std=c++23','-O1','-g','-static','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(temp),'-I'+str(REC),str(ROOT/'tests/otg_discovery_test.cpp'),'-o',str(temp/'test')],check=True)
  for name in CASES:
   jail=temp/name;jail.mkdir();(jail/'test').write_bytes((temp/'test').read_bytes());(jail/'test').chmod(0o755)
   r=subprocess.run(['chroot',str(jail),'/test',name,pattern],capture_output=True,text=True,timeout=20)
   cases.append(dict(case=name,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
   print(name,'PASS' if r.returncode==0 else 'FAIL',r.stderr,flush=True)
 sources=[a.source,a.header,REC/'partition.cpp',REC/'sysfs_device_match.hpp',fstab,Path(__file__).resolve(),ROOT/'tests/otg_discovery_test.cpp',ROOT/'tests/nested_partition_path_test.py']
 report=dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',scope=__doc__,pattern=pattern,cases=cases,sources={str(p):sha(p) for p in sources})
 a.report.write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
