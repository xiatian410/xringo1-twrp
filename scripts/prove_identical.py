#!/usr/bin/env python3
"""Prove the modules in the device tree are byte-identical to the ones the
stock vendor_boot ramdisk loads.

This is the only ABI evidence that matters: the stock recovery boots with
these exact .ko files against the exact kernel in boot.img, so if our copies
are identical the module_layout / __versions stamps cannot be the problem.
"""
import hashlib
import os
import sys

sys.path.insert(0, '/root/AAA/xringo1-twrp/scripts')
from repack_ramdisk import parse_cpio  # noqa: E402
from lz4legacy import decompress  # noqa: E402

VB_RAMDISK = '/root/AAA/xringo1-twrp/imgs/extracted/vendor_boot.img.vendor_ramdisk'
VB_MODROOT = 'lib/modules/6.18.21-android17-5-maybe-dirty-4k/'
OURS = '/root/AAA/xringo1-twrp/dtsrc/O1_asic_dual/recovery/root/lib/modules/6.18'

raw = open(VB_RAMDISK, 'rb').read()
blob = decompress(raw) if raw[:4] == b'\x02\x21\x4c\x18' else raw
ents = parse_cpio(blob)

vb = {}
for name, mode, uid, gid, nlink, mtime, size, dm, dn, rm, rn, data in ents:
    if name.startswith(VB_MODROOT) and name.endswith('.ko'):
        vb[name.rsplit('/', 1)[-1]] = (hashlib.md5(data).hexdigest(), size)

ours = {}
for f in sorted(os.listdir(OURS)):
    if f.endswith('.ko'):
        p = os.path.join(OURS, f)
        ours[f] = (hashlib.md5(open(p, 'rb').read()).hexdigest(), os.path.getsize(p))

print(f'vendor_boot .ko : {len(vb)}')
print(f'device tree .ko : {len(ours)}')

identical = [n for n in vb if n in ours and vb[n][0] == ours[n][0]]
differ = [n for n in vb if n in ours and vb[n][0] != ours[n][0]]
absent = [n for n in vb if n not in ours]

print(f'\nbyte-identical  : {len(identical)}')
print(f'DIFFERENT       : {len(differ)}')
for n in differ:
    print(f'    {n}: vb={vb[n][0]} {vb[n][1]}B  ours={ours[n][0]} {ours[n][1]}B')
print(f'MISSING from tree: {len(absent)} {absent[:5]}')

bonus = [n for n in ours if n not in vb]
print(f'\nin tree but not in vendor_boot ({len(bonus)}):')
for n in bonus:
    print(f'    {n}  {ours[n][1]}B')

print('\nRESULT:', 'ALL STOCK MODULES BYTE-IDENTICAL' if not differ and not absent
      else 'DIFFERENCES FOUND - see above')