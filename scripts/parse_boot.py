#!/usr/bin/env python3
"""Split AOSP boot/vendor_boot v3/v4 with bounds-checked header parsing.

V3 boot header is 1580 bytes; v4 is 1584. The u32 at offset 1580 in
v4 is signature_size, not extra_cmdline_size. Signatures are bounded by that
field. Vendor ramdisk names are 32 bytes; board_id is a separate 16-u32 array.
Unsupported v0-v2 headers are rejected rather than interpreted as v4.
Usage: parse_boot.py boot_or_vendor_boot.img output_directory
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from firmware_facts import boot_parts


def main(path, directory):
    path, out = Path(path), Path(directory)
    facts, pieces = boot_parts(path.read_bytes())
    print(json.dumps(facts, indent=2))
    out.mkdir(parents=True, exist_ok=True)
    for name, data in pieces.items():
        target = out / (path.name + '.' + name)
        if target.is_symlink():
            raise ValueError('refusing output symlink')
        target.write_bytes(data)
        print(target, len(data))


if __name__ == '__main__':
    main(*sys.argv[1:])
