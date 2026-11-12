#!/usr/bin/env python3
"""Extract __versions / vermagic facts from .ko files using readelf."""
import glob
import os
import re
import subprocess
import sys


def readelf_sections(ko):
    out = subprocess.run(['readelf', '-SW', ko], capture_output=True, text=True).stdout
    secs = {}
    for line in out.splitlines():
        m = re.match(r'\s*\[\s*\d+\]\s+(\S+)\s+(\S+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)', line)
        if m:
            secs[m.group(1)] = dict(type=m.group(2), addr=m.group(3), off=m.group(4), size=m.group(5))
    return secs


def readelf_vermagic(ko):
    out = subprocess.run(['modinfo', '-F', 'vermagic', ko], capture_output=True, text=True)
    v = out.stdout.strip()
    return v or None


def readelf_versions(ko):
    """Dump the __versions section (modversion_info entries)."""
    out = subprocess.run(['readelf', '-x', '__versions', ko], capture_output=True, text=True)
    if out.returncode != 0:
        return []
    rows = []
    for line in out.stdout.splitlines():
        m = re.match(r'\s*([0-9a-f]+)\s+((?:[0-9a-f]{8}\s+){1,4})', line)
        if m:
            rows.append(m.group(2).split())
    return rows


def find_module_layout_raw(ko):
    """Search __versions bytes for the module_layout record.

    struct modversion_info { unsigned long crc; char name[MODULE_NAME_LEN]; }
    On a 64-bit target crc is 8 bytes; the section is a flat array.
    """
    b = open(ko, 'rb').read()
    idx = b.find(b'module_layout\x00')
    if idx < 0:
        return None
    start = idx - 8
    if start < 0:
        return None
    crc = b[start:idx]
    return crc.hex(), int.from_bytes(crc, 'little')


def main(argv):
    for d in argv[1:]:
        files = sorted(glob.glob(os.path.join(d, '*.ko')))
        if not files:
            print(f'{d}: no .ko (extraction dir uses subdirs?)')
            continue
        print(f'== {d} ({len(files)} .ko)')
        sample = files[0]
        print(f'   sample {os.path.basename(sample)}')
        print(f'   vermagic (modinfo): {readelf_vermagic(sample)}')
        ml = find_module_layout_raw(sample)
        print(f'   module_layout crc raw: {ml}')
        sets = {}
        for f in files:
            ml = find_module_layout_raw(f)
            key = ml[1] if ml else None
            sets.setdefault(key, []).append(os.path.basename(f))
        print(f'   distinct module_layout CRCs: {len(sets)}')
        for k, v in sets.items():
            print(f'      {k}  [{len(v)}]  e.g. {v[:3]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))