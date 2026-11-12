#!/usr/bin/env python3
"""Print the stock first_stage fstab from vendor_boot for reference."""
import sys

sys.path.insert(0, '/root/AAA/xringo1-twrp/scripts')
from repack_ramdisk import parse_cpio  # noqa: E402
from lz4legacy import decompress  # noqa: E402

SRC = '/root/AAA/xringo1-twrp/imgs/extracted/vendor_boot.img.vendor_ramdisk'
d = open(SRC, 'rb').read()
blob = decompress(d) if d[:4] == b'\x02\x21\x4c\x18' else d
ents = {e[0]: e for e in parse_cpio(blob)}

key = 'first_stage_ramdisk/fstab.O1_asic'
if key not in ents:
    print('missing', key)
    sys.exit(1)
text = ents[key][11].decode(errors='replace')
for line in text.splitlines():
    s = line.strip()
    if not s or s.startswith('#'):
        continue
    if any(k in s for k in ('mi_ext', 'mi_product', 'userdata', 'metadata')):
        print(s)