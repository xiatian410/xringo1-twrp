#!/usr/bin/env python3
"""Remove the duplicate default-version Health declaration; retain built Health v4."""
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parent))
import repack_ramdisk as rd
from lz4legacy import decompress
from make_fix_images import pack
root=Path(__file__).resolve().parent.parent
name='system/etc/vintf/manifest/recovery-device.xml'
p=root/'dtsrc/O1_asic_dual/recovery/root'/name
xml=ET.fromstring(p.read_text())
for hal in list(xml.findall('hal')):
    if hal.findtext('name')=='android.hardware.health': xml.remove(hal)
text=ET.tostring(xml,encoding='unicode')+'\n'
p.write_text(text)
base=(root/'imgs/built/twrp-recovery-fstabfix.img').read_bytes()
size=struct.unpack_from('<I',base,12)[0]
original=rd.parse_cpio(decompress(base[4096:4096+size]))
Path('/tmp/dijun-halfix-input.rd').write_bytes(base[4096:4096+size])
assert rd.main(['repack_ramdisk','/tmp/dijun-halfix-input.rd','/tmp/dijun-halfix.rd','--write',name,str(p)])==0
new=rd.parse_cpio(decompress(Path('/tmp/dijun-halfix.rd').read_bytes()))
a={e[0]:e for e in original}; b={e[0]:e for e in new}
assert a.keys()==b.keys()
assert [n for n in a if a[n]!=b[n]]==[name]
health=[]
for n,e in b.items():
    if '/vintf/manifest/' in n and n.endswith('.xml'):
        for h in ET.fromstring(e[11]).findall('hal'):
            if h.findtext('name')=='android.hardware.health': health.append((n,h.findtext('version','1')))
assert len(health)==1 and health[0][1]=='4',health
print('Verified unique Health declaration:',health)
pack(base,'/tmp/dijun-halfix.rd',str(root/'imgs/built/twrp-recovery-halfix.img'))
