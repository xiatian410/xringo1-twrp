#!/usr/bin/env python3
"""Keep a missing KeyMint provider from causing recovery-wide fatal reboots."""
from pathlib import Path
import struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import repack_ramdisk as rd
from lz4legacy import decompress
from make_fix_images import pack
root=Path(__file__).resolve().parent.parent
base=(root/'imgs/built/twrp-recovery-halfix.img').read_bytes()
size=struct.unpack_from('<I',base,12)[0]
entries=rd.parse_cpio(decompress(base[4096:4096+size]))
name='system/etc/init/keystore2.rc'
a={e[0]:e for e in entries}
old=a[name][11].decode()
assert 'critical window=0' in old
fixed='\n'.join(l for l in old.splitlines() if not l.strip().startswith('critical') and 'Reboot to bootloader if Keystore' not in l)+'\n'
fixed=fixed.replace('    seclabel u:r:recovery:s0','    # Missing vendor KeyMint must not reboot the recovery environment.\n    seclabel u:r:recovery:s0')
p=root/'dtsrc/O1_asic_dual/recovery/root'/name
p.parent.mkdir(parents=True,exist_ok=True); p.write_text(fixed)
source=Path('/root/AAA/twrp/bootable/recovery/etc/init/keystore2.rc')
if source.exists() and source.read_text()==old: source.write_text(fixed)
Path('/tmp/dijun-keystore-input.rd').write_bytes(base[4096:4096+size])
assert rd.main(['repack_ramdisk','/tmp/dijun-keystore-input.rd','/tmp/dijun-keystore.rd','--write',name,str(p)])==0
b={e[0]:e for e in rd.parse_cpio(decompress(Path('/tmp/dijun-keystore.rd').read_bytes()))}
assert a.keys()==b.keys()
assert [n for n in a if a[n]!=b[n]]==[name]
assert not any(l.strip().startswith('critical') for l in b[name][11].decode().splitlines())
assert 'start keystore2' in fixed
print('Verified: only keystore2.rc changed; service startup/retry preserved; no critical directive.')
pack(base,'/tmp/dijun-keystore.rd',str(root/'imgs/built/twrp-recovery-keystorefix.img'))
