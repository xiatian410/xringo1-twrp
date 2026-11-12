#!/usr/bin/env python3
"""Verify a built recovery image against its base: header, ramdisk, vbmeta tail."""
import struct
import sys

PAGE = 4096
FOOTER_SIZE = 64


def layout(p):
    d = open(p, 'rb').read()
    rd_size = struct.unpack('<I', d[12:16])[0]
    rd_end = PAGE + (rd_size + PAGE - 1) // PAGE * PAGE
    footer = d[-FOOTER_SIZE:]
    ver_major, ver_minor = struct.unpack('>II', footer[4:12])
    orig, vb_off, vb_size = struct.unpack('>QQQ', footer[12:36])
    return dict(path=p, size=len(d), rd_size=rd_size, rd_end=rd_end,
                ver=(ver_major, ver_minor), orig=orig, vb_off=vb_off,
                vb_size=vb_size, data=d)


def main(argv):
    base = layout(argv[1])
    for p in argv[2:]:
        new = layout(p)
        print(f'== {p}')
        print(f'   size {new["size"]}  ramdisk {new["rd_size"]}  end {new["rd_end"]}')
        print(f'   footer ver {new["ver"]} orig={new["orig"]} vb_off={new["vb_off"]} '
              f'vb_size={new["vb_size"]}')
        ok = new['orig'] == new['rd_end'] and new['vb_off'] == new['rd_end']
        print(f'   footer consistent with ramdisk end: {ok}')

        # vbmeta blob region comparison against base
        b_off, b_sz = base['vb_off'], base['vb_size']
        n_off, n_sz = new['vb_off'], new['vb_size']
        bb = base['data'][b_off:b_off + b_sz]
        nb = new['data'][n_off:n_off + n_sz]
        if b_sz == n_sz:
            same = bb == nb
            print(f'   vbmeta blob ({n_sz} B @ {n_off}): '
                  f'{"IDENTICAL to base" if same else "DIFFERS from base"}')
            if not same:
                bnz = sum(1 for x in bb if x)
                nnz = sum(1 for x in nb if x)
                print(f'      base non-zero {bnz}, new non-zero {nnz}')
                for i in range(min(len(bb), len(nb))):
                    if bb[i] != nb[i]:
                        print(f'      first diff at +{i}: base {bb[i]:02x} new {nb[i]:02x}')
                        break
        else:
            print(f'   vbmeta size mismatch: base {b_sz} new {n_sz}')

        # what sits between ramdisk end and the footer
        nz = sum(1 for x in new['data'][new['rd_end']:-FOOTER_SIZE] if x)
        print(f'   non-zero bytes between ramdisk end and footer: {nz}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))