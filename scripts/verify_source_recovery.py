#!/usr/bin/env python3
"""Inspect an actual source-built recovery before presenting it for testing."""
from pathlib import Path
import hashlib,stat,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from repack_ramdisk import parse_cpio
from lz4legacy import decompress

def main(path):
 b=Path(path).read_bytes();ks,rs=struct.unpack_from('<II',b,8);assert ks==0
 assert struct.unpack_from('<I',b,16)[0]==0, 'ramdisk-only recovery must retain the stock header profile'
 stock=bytearray(Path('imgs/recovery.img').read_bytes()[:4096]); struct.pack_into('<I',stock,12,rs)
 assert bytes(stock)==b[:4096], 'header differs from stock beyond ramdisk length'
 print('Entire header page matches stock apart from ramdisk size.')
 ram=b[4096:4096+rs];ents={e[0]:e for e in parse_cpio(decompress(ram))}
 props={}
 for name,e in ents.items():
  if name.endswith(('prop.default','default.prop','build.prop')) and stat.S_ISREG(e[1]):
   for l in e[11].decode(errors='replace').splitlines():
    if l and not l.startswith('#') and '=' in l:
     k,v=l.split('=',1); props.setdefault(k,[]).append((name,v))
 for k,expected in [('ro.build.version.release','16'),('ro.build.version.security_patch','2026-09-01'),('ro.vendor.build.security_patch','2026-09-01'),('ro.product.first_api_level','35')]:
  assert k in props,(k,'absent')
  assert all(v==expected for _,v in props[k]),(k,props[k])
  print(k,props[k])
 crypto=ents['system/etc/dijun-crypto-profile.prop'][11].decode()
 assert 'ro.build.version.release=17' in crypto
 helper=ents['system/bin/dijun-prepare-mitee.sh'][11].decode()
 assert '/system/bin/resetprop -n' in helper and helper.index('/system/bin/resetprop -n') < helper.index('setprop twrp.mitee.prepared 1')
 print('OTA crypto profile applied and checked before HAL startup:',crypto.strip())
 for p in ['vendor/bin/tee-supplicant','vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee','vendor/bin/hw/android.hardware.gatekeeper-service.mitee']:
  e=ents[p];assert stat.S_ISREG(e[1]) and e[1]&0o111,(p,oct(e[1]))
  assert e[11]==(Path('imgs/firmware')/p).read_bytes()
 assert not [n for n in ents if n.startswith('lib/modules/') and n.rsplit('/',1)[-1] in ('modules.load','modules.load.recovery')], 'Do not override stock vendor_boot first-stage loading'
 print('First-stage module lists absent: vendor_boot owns boot-critical loading.')
 assert b'critical' not in b'\n'.join(l for l in ents['system/etc/init/keystore2.rc'][11].splitlines() if not l.strip().startswith(b'#'))
 print('Verified firmware properties, original vendor ELF bytes/modes, stock vendor_boot module-loading ownership, non-critical keystore2.')
 print('SIZE',len(b),'RAMDISK',rs,'MD5',hashlib.md5(b).hexdigest())
if __name__=='__main__':main(sys.argv[1])
