#!/usr/bin/env python3
"""Inventory the stock vendor_boot ramdisk module tree."""
import os
import sys

sys.path.insert(0, '/root/AAA/xringo1-twrp/scripts')
from repack_ramdisk import parse_cpio  # noqa: E402
from lz4legacy import decompress  # noqa: E402

SRC = '/root/AAA/xringo1-twrp/imgs/extracted/vendor_boot.img.vendor_ramdisk'
d = open(SRC, 'rb').read()
blob = decompress(d) if d[:4] == b'\x02\x21\x4c\x18' else d
ents = parse_cpio(blob)
byname = {e[0]: e for e in ents}

root = 'lib/modules/6.18.21-android17-5-maybe-dirty-4k/'
ko = [n for n in byname if n.startswith(root) and n.endswith('.ko')]
print('vendor_boot .ko:', len(ko))

for f in ('modules.load', 'modules.load.recovery', 'modules.order',
          'modules.blocklist', 'modules.softdep', 'modules.alias'):
    e = byname.get(root + f)
    if not e:
        print(f'{f}: absent')
        continue
    lines = e[11].decode(errors='replace').splitlines()
    lines = [x for x in lines if x.strip()]
    print(f'{f}: {len(lines)} lines, {e[6]} bytes')
    if f in ('modules.load', 'modules.blocklist'):
        for x in lines:
            print('    ' + x)

print('\n--- .ko whose basename mentions touch/shub/synaptics/nt36 ---')
for n in ko:
    b = n.rsplit('/', 1)[-1]
    if any(k in b for k in ('touch', 'shub', 'synaptics', 'nt36')):
        print('   ', n[len(root):], byname[n][6])

print('\n--- basenames in modules.load.recovery but NOT in modules.load ---')
rl = {x.strip().rsplit('/', 1)[-1] for x in byname[root + 'modules.load.recovery'][11].decode().splitlines() if x.strip()}
nl = {x.strip().rsplit('/', 1)[-1] for x in byname[root + 'modules.load'][11].decode().splitlines() if x.strip()}
print('recovery only:', sorted(rl - nl))
print('normal only  :', sorted(nl - rl))
print('ko not in either list:', sorted({n.rsplit('/', 1)[-1] for n in ko} - rl - nl))