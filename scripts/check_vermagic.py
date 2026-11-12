#!/usr/bin/env python3
"""Dump vermagic and module_layout CRC from every .ko in a set, and the
kernel release string from a boot image, so ABI compatibility can be judged
without flashing anything.
"""
import glob
import os
import re
import struct
import sys

VERMAGIC_RE = re.compile(rb'([0-9]+\.[0-9]+\.[0-9]+[^\x00]{0,80}?SMP[^\x00]{0,80})')


def vermagic(blob):
    m = VERMAGIC_RE.search(blob)
    return m.group(1).decode(errors='replace') if m else None


def module_layout_crc(blob):
    """Find the __versions entry for module_layout: struct modversion_info is
    { unsigned long crc; char name[MODULE_NAME_LEN]; } but the CRC field in
    modversions is stored as a *string* of 8 hex chars in the ELF section by
    some builds.  Try both shapes.
    """
    idx = blob.find(b'module_layout')
    if idx < 0:
        return None
    # the 8 bytes immediately preceding the name in __versions
    before = blob[max(0, idx - 8):idx]
    cands = {
        'u64_le': struct.unpack('<Q', before)[0] if len(before) == 8 else None,
        'u32_le': struct.unpack('<I', before[4:8])[0] if len(before) == 8 else None,
        'ascii': before.decode(errors='replace'),
    }
    return cands


def scan_dir(path, label):
    files = sorted(glob.glob(os.path.join(path, '*.ko')))
    print(f'\n=== {label}: {path} ({len(files)} .ko) ===')
    groups = {}
    for f in files:
        b = open(f, 'rb').read()
        v = vermagic(b)
        groups.setdefault(v, []).append(os.path.basename(f))
    for v, names in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f'  [{len(names):3d}] {v}')
        if len(names) <= 3:
            print(f'        {names}')
    return groups


def kernel_release(boot_img):
    d = open(boot_img, 'rb').read()
    ks = struct.unpack('<I', d[8:12])[0]
    page = 4096
    k = d[page:page + ks] if ks else d
    m = re.search(rb'Linux version ([^\x00\x20\)]+)', k)
    return m.group(1).decode(errors='replace') if m else None


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    boot = argv[1]
    print(f'kernel release from {boot}: {kernel_release(boot)}')
    for p in argv[2:]:
        scan_dir(p, os.path.basename(p.rstrip('/')))

    # module_layout CRC comparison across sets
    print('\n=== module_layout CRC by set ===')
    for p in argv[2:]:
        seen = {}
        for f in sorted(glob.glob(os.path.join(p, '*.ko'))):
            c = module_layout_crc(open(f, 'rb').read())
            if c:
                key = (c['u32_le'], c['ascii'])
                seen.setdefault(key, []).append(os.path.basename(f))
        print(f'  {p}')
        for k, v in sorted(seen.items(), key=lambda kv: -len(kv[1])):
            print(f'     u32={k[0]} ascii={k[1]!r}  [{len(v)} modules]')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))