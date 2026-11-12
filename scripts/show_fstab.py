#!/usr/bin/env python3
"""Show the fstab that is actually inside a built recovery image."""
import struct
import sys

sys.path.insert(0, '/root/AAA/xringo1-twrp/scripts')
from repack_ramdisk import parse_cpio  # noqa: E402
from lz4legacy import decompress  # noqa: E402

img = sys.argv[1]
d = open(img, 'rb').read()
rs = struct.unpack('<I', d[12:16])[0]
ram = d[4096:4096 + rs]
blob = decompress(ram) if ram[:4] == b'\x02\x21\x4c\x18' else ram
ents = {e[0]: e for e in parse_cpio(blob)}

print('fstab-ish entries:')
for k in sorted(ents):
    if 'fstab' in k:
        print(f'   {k}  {ents[k][6]} B')

for name in ('etc/recovery.fstab', 'system/etc/recovery.fstab'):
    if name in ents:
        t = ents[name][11].decode(errors='replace')
        print(f'\n--- {name}: lines mentioning mi_ext / mi_product ---')
        n = 0
        for line in t.splitlines():
            if 'mi_ext' in line or 'mi_product' in line:
                print('   ' + line)
                n += 1
        print(f'   ({n} lines)')