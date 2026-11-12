#!/usr/bin/env python3
"""Verify the device-fix candidate and retain the validated crypto baseline."""
from pathlib import Path
import hashlib,json,stat,struct,sys
from repack_ramdisk import parse_cpio
from lz4legacy import decompress
from verify_source_recovery import main as verify_boot
BASE=Path(__file__).resolve().parents[1]

def entries(path):
 b=Path(path).read_bytes();rs=struct.unpack_from('<I',b,12)[0]
 return b,{e[0]:e for e in parse_cpio(decompress(b[4096:4096+rs]))}

def main(path):
 verify_boot(path)
 data,ent=entries(path)
 baseline,old=entries(BASE/'imgs/verified/twrp-recovery-mitee-bootfix.img')
 assert hashlib.md5(baseline).hexdigest()=='5819f969bceb558cf734d5ae5608e211'
 preserved=[]
 for n,e in old.items():
  if n.startswith(('system/lib64/mitee/','vendor/bin/','vendor/mitee/ta/','system/etc/vintf/manifest/')) or n in [
    'system/bin/dijun-prepare-mitee.sh','system/etc/dijun-crypto-profile.prop',
    'system/etc/init/dijun-mitee.rc','system/etc/init/keystore2.rc','etc/recovery.fstab',
    'system/etc/recovery.fstab','system/etc/init/android.hardware.boot-service.xring.recovery.rc']:
   assert n in ent and e[1:4]==ent[n][1:4] and e[11]==ent[n][11],n
   preserved.append(n)
 # These exact built artifacts must reach the ramdisk (no stale relink stamp).
 out=Path('/root/AAA/twrp/out/target/product/O1_asic')
 for n in ['system/bin/recovery','system/lib64/libgui2.so','system/lib64/libtwrpminui.so','system/lib64/libtwrpmtp-ffs.so']:
  if n.endswith('libgui2.so'):
   artifact=Path('/root/AAA/twrp/out/soong/.intermediates/bootable/recovery/gui2/libgui2/android_recovery_arm64_armv8-a_shared/libgui2.so')
  elif n.endswith('libtwrpmtp-ffs.so'):
   artifact=Path('/root/AAA/twrp/out/soong/.intermediates/bootable/recovery/mtp/libtwrpmtp-ffs/android_recovery_arm64_armv8-a_shared/libtwrpmtp-ffs.so')
  elif n.endswith('/recovery'):
   artifact=out/'recovery/root'/n
  else:
   artifact=out/n
  assert ent[n][11]==artifact.read_bytes(),f'stale binary {n}'
 for n in ['init.recovery.usb.rc','init.recovery.O1_asic.rc','system/etc/init/dijun-mitee.rc','system/etc/init/keystore2.rc']:
  assert ent[n][11]==(out/'recovery/root'/n).read_bytes(),f'stale init script {n}'
 usb=ent['init.recovery.usb.rc'][11].decode()
 assert 'mount functionfs mtp /dev/usb-ffs/mtp' in usb
 assert 'property:sys.usb.ffs.mtp.ready=1' in usb and 'property:sys.usb.ffs.ready=1' in usb
 assert 'android_usb/android0' not in usb
 firmware_path='/lib/firmware' if 'lib/firmware/cs40l26.wmfw' in ent else '/vendor/firmware'
 assert f'write /sys/module/firmware_class/parameters/path {firmware_path}' in ent['init.recovery.O1_asic.rc'][11].decode()
 props=ent['prop.default'][11].decode()
 assert 'ro.twrp.default_timezone=CST-8' in props
 assert 'ro.twrp.default_timezone_selection=TAIST-8;TAIDT' in props
 root='lib/modules/6.18/'
 mod='xring_audio_hw_third.ko'
 assert stat.S_ISREG(ent[root+mod][1])
 assert ent[root+mod][11]==(BASE/'imgs/firmware/vendor_dlkm/lib/modules'/mod).read_bytes()
 dep=ent[root+'modules.dep'][11].decode()
 row=next(l for l in dep.splitlines() if l.startswith(mod+':'))
 for n in row.split(':',1)[1].split():assert root+n in ent,n
 fw=[]
 for f in (BASE/'imgs/firmware/vendor/firmware').glob('cs40l26*'):
  n='vendor/firmware/'+f.name
  assert ent[n][11]==f.read_bytes() and stat.S_ISREG(ent[n][1]),n
  fw.append(n)
 assert len(fw)==9
 odm_fw=[]
 if firmware_path=='/lib/firmware':
  inventory=json.loads((BASE/'dtsrc/O1_asic_dual/prebuilt/dijun/haptics/odm-firmware-inventory.json').read_text())
  for item in inventory:
   n='lib/firmware/'+Path(item['source']).name
   assert n in ent and stat.S_ISREG(ent[n][1]),n
   assert hashlib.sha256(ent[n][11]).hexdigest()==item['sha256'],n
   assert ent[n][11]==(BASE/item['source']).read_bytes(),n
   odm_fw.append(n)
  assert len(odm_fw)==11
  dirs=ent['system/etc/ueventd.rc'][11].decode()
  dirs=next(l.split()[1:] for l in dirs.splitlines() if l.startswith('firmware_directories '))
  assert dirs.index('/odm/firmware/')<dirs.index('/vendor/firmware/')
  # Preserve differing per-product parameters; do not flatten same-name files.
  for name in ['cs40l26-a2h.bin','cs40l26-dbc.bin']:
   assert ent['vendor/firmware/'+name][11]!=ent['lib/firmware/'+name][11]
 assert len(data)==104857600
 result={'image':str(Path(path).resolve()),'md5':hashlib.md5(data).hexdigest(),
  'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),
  'ramdisk_size':struct.unpack_from('<I',data,12)[0],
  'crypto_files_identical_to_verified_baseline':preserved,'original_cirrus_firmware':fw,
  'original_odm_firmware':odm_fw,'kernel_firmware_path':firmware_path,
  'haptic_module_sha256':hashlib.sha256(ent[root+mod][11]).hexdigest(),
  'validation':'source build and static ramdisk comparison; separate reports cover host regressions and init verification; hardware unverified (offline-only task)'}
 Path(path).with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(f'PASS: {len(preserved)} baseline crypto files retained; USB FFS, UTC+8 default, Cirrus module/firmware, fresh GUI binaries verified.')
if __name__=='__main__':main(sys.argv[1])
