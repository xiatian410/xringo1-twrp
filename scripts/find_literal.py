#!/usr/bin/env python3
"""Locate the compiled-in TW_LOAD_VENDOR_MODULES string inside a recovery ramdisk."""
import struct
import sys

sys.path.insert(0, '/root/AAA/xringo1-twrp/scripts')
from repack_ramdisk import parse_cpio  # noqa: E402
from lz4legacy import decompress  # noqa: E402

IMG = sys.argv[1] if len(sys.argv) > 1 else '/root/AAA/xringo1-twrp/imgs/built/twrp-recovery-noload.img'
NEEDLE = b'ab_slot_bootable_ctrl.ko apb_timer.ko'

d = open(IMG, 'rb').read()
rs = struct.unpack('<I', d[16:20])[0]
ram = d[4096:4096 + rs]
blob = decompress(ram) if ram[:4] == b'\x02\x21\x4c\x18' else ram
ents = parse_cpio(blob)

hits = 0
for e in ents:
    if NEEDLE in e[11]:
        off = e[11].find(NEEDLE)
        print('HIT entry %-60s size=%d off=%d' % (e[0], e[6], off))
        print('   ctx: %r' % e[11][max(0, off - 60):off + 160])
        hits += 1
print('total hits', hits)
