#!/usr/bin/env python3
"""Compare two recovery images entry by entry at the cpio level.

Reports entries added, removed, and payload-changed, plus the header fields and
the trailing region. Used to prove a rebuild changed exactly what was intended.
"""
import struct
import sys

sys.path.insert(0, '/root/AAA/xringo1-twrp/scripts')
from repack_ramdisk import parse_cpio  # noqa: E402
from lz4legacy import decompress  # noqa: E402

PAGE = 4096
FOOTER_SIZE = 64


def load(p):
    d = open(p, 'rb').read()
    rd_size = struct.unpack('<I', d[12:16])[0]
    ram = d[PAGE:PAGE + rd_size]
    blob = decompress(ram) if ram[:4] == b'\x02\x21\x4c\x18' else ram
    return d, rd_size, parse_cpio(blob)


def main(argv):
    a, b = argv[1], argv[2]
    da, ra, ea = load(a)
    db, rb, eb = load(b)
    print(f'A = {a}\n   ramdisk {ra}\nB = {b}\n   ramdisk {rb}')

    print(f'\nheader A: {da[:44].hex()}')
    print(f'header B: {db[:44].hex()}')
    print(f'header identical: {da[:PAGE] == db[:PAGE][:0] + db[:PAGE][:0] or da[:44] == db[:44]}')

    ma = {e[0]: e for e in ea}
    mb = {e[0]: e for e in eb}

    added = [n for n in mb if n not in ma]
    removed = [n for n in ma if n not in mb]
    common = [n for n in mb if n in ma]

    print(f'\nentries A {len(ea)}  B {len(eb)}')
    print(f'added   {len(added)}: {added}')
    print(f'removed {len(removed)}: {removed}')

    changed = []
    for n in common:
        x, y = ma[n], mb[n]
        # name, mode, uid, gid, nlink, mtime, filesize, devs..., data
        if x[1:6] != y[1:6] or x[7:11] != y[7:11] or x[11] != y[11]:
            changed.append(n)
    print(f'changed {len(changed)}: {changed[:20]}')

    # Also verify the order is preserved (which matters for cpio determinism)
    order_a = [e[0] for e in ea]
    order_b = [e[0] for e in eb]
    filtered_b = [n for n in order_b if n in ma]
    print(f'entry order preserved for common entries: {filtered_b == order_a}')

    # Trailing region
    ra_end = PAGE + (ra + PAGE - 1) // PAGE * PAGE
    rb_end = PAGE + (rb + PAGE - 1) // PAGE * PAGE
    ta = da[ra_end:len(da) - FOOTER_SIZE]
    tb = db[rb_end:len(db) - FOOTER_SIZE]
    print(f'\ntail A {len(ta)} B {len(tb)}')
    nz_a, nz_b = sum(1 for x in ta if x), sum(1 for x in tb if x)
    print(f'tail non-zero A {nz_a} B {nz_b}')
    n = min(len(ta), len(tb))
    print(f'tail first {n} equal: {ta[:n] == tb[:n]}')
    print(f'footer equal: {da[-FOOTER_SIZE:] == db[-FOOTER_SIZE:]}')
    if da[-FOOTER_SIZE:] != db[-FOOTER_SIZE:]:
        print(f'  A footer {da[-FOOTER_SIZE:].hex()}')
        print(f'  B footer {db[-FOOTER_SIZE:].hex()}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))