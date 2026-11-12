#!/usr/bin/env python3
"""Legacy recovery-image packing helpers.

The old list variants are retired: their added cpio list accidentally inherited
its parent directory's inode type. A filename/content-only inventory did not
model init's behavior. libmodprobe canonicalizes load entries to basenames, so
relative-path text alone was not proof of the old vlist failure mechanism.
Current source builds defer first-stage module loading to stock vendor_boot.
The pack() helper remains used by the historical reproducibility scripts.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import repack_ramdisk  # noqa: E402
from repack_ramdisk import parse_cpio  # noqa: E402
from lz4legacy import decompress  # noqa: E402

ROOT = '/root/AAA/xringo1-twrp'
VB_RAMDISK = f'{ROOT}/imgs/extracted/vendor_boot.img.vendor_ramdisk'
VB_MODROOT = 'lib/modules/6.18.21-android17-5-maybe-dirty-4k'
FLAT_DIR = f'{ROOT}/dtsrc/O1_asic_dual/recovery/root/lib/modules/6.18'
FSTAB_SRC = f'{ROOT}/dtsrc/O1_asic_dual/recovery.fstab'
BASE_IMG = f'{ROOT}/imgs/built/twrp-recovery-noload.img'
OUT_IMG = f'{ROOT}/imgs/built/twrp-recovery-flatlist.img'
OUT_IMG_FULL = f'{ROOT}/imgs/built/twrp-recovery-flatfull.img'

PARTITION_SIZE = 104857600
PAGE = 4096
FOOTER_SIZE = 64

# Boot image v3/v4 header field offsets and the total header size.
OFF_KERNEL_SIZE = 8
OFF_RAMDISK_SIZE = 12
OFF_OS_VERSION = 16
OFF_HEADER_SIZE = 20
HEADER_SIZE = 1584

# AvbFooter: magic[4] ver_major(u32) ver_minor(u32)
#            original_image_size(u64) vbmeta_offset(u64) vbmeta_size(u64)
#            reserved[28]      -- every integer is big endian
OFF_F_ORIG = 12
OFF_F_VBMETA_OFF = 20
OFF_F_VBMETA_SIZE = 28


def read_vb():
    raw = open(VB_RAMDISK, 'rb').read()
    blob = decompress(raw) if raw[:4] == b'\x02\x21\x4c\x18' else raw
    return {e[0]: e for e in parse_cpio(blob)}


def stock_list(vb):
    key = f'{VB_MODROOT}/modules.load.recovery'
    if key not in vb:
        sys.exit(f'FATAL: {key} not present in stock vendor_boot ramdisk')
    return [x.strip() for x in vb[key][11].decode().splitlines() if x.strip()]


def flat_modules():
    return sorted(f for f in os.listdir(FLAT_DIR) if f.endswith('.ko'))


def parse_dep(path):
    dep = {}
    for line in open(path):
        lhs, sep, rhs = line.strip().partition(':')
        if sep:
            dep[lhs.strip()] = rhs.split()
    return dep


def to_flat(stock, flats):
    """Reorder nothing: map each stock relative path to its flat basename."""
    setf = set(flats)
    out, missing = [], []
    for entry in stock:
        base = entry.rsplit('/', 1)[-1]
        (out if base in setf else missing).append(base if base in setf else entry)
    return out, missing


def report():
    vb = read_vb()
    stock = stock_list(vb)
    flats = flat_modules()
    flat, missing = to_flat(stock, flats)
    dep = parse_dep(os.path.join(FLAT_DIR, 'modules.dep'))

    print(f'stock modules.load.recovery entries : {len(stock)}')
    print(f'flat .ko files in the device tree   : {len(flats)}')
    print(f'entries resolvable to a flat .ko    : {len(flat)}')
    print(f'entries with no matching file       : {len(missing)}')
    for m in missing:
        print(f'    MISSING {m}')

    nodep = [m for m in flat if m not in dep]
    dangling = []
    have = set(flats)
    for m in flat:
        for d in dep.get(m, []):
            if d not in have:
                dangling.append((m, d))
    print(f'listed without modules.dep row      : {len(nodep)} {nodep[:5]}')
    print(f'hard deps missing from the dir      : {len(dangling)} {dangling[:5]}')

    listed = set(flat)
    extras = [f for f in flats if f not in listed]
    print(f'\nmodules NOT in the stock list ({len(extras)}) - '
          f'these stay for TWRP\'s later load:')
    for e in extras:
        print('    ' + e)
    return flat, missing


def build_variant(extras, out_img):
    """Build a recovery image whose first-stage list is the stock 139 (rewritten
    to flat basenames) optionally followed by extra modules TWRP needs."""
    vb = read_vb()
    stock = stock_list(vb)
    flats = flat_modules()
    flat, missing = to_flat(stock, flats)
    if missing:
        sys.exit(f'FATAL: {len(missing)} entries unresolvable; refusing to build')

    if extras:
        dep = parse_dep(os.path.join(FLAT_DIR, 'modules.dep'))
        have = set(flats)
        bad = [e for e in extras if e not in have]
        if bad:
            sys.exit(f'FATAL: extra modules not on disk: {bad}')
        dangling = [(e, d) for e in extras for d in dep.get(e, []) if d not in have]
        if dangling:
            sys.exit(f'FATAL: extra modules have unresolvable deps: {dangling}')
        flat = flat + [e for e in extras if e not in set(flat)]

    listfile = f'/tmp/modules.load.recovery.{len(flat)}'
    with open(listfile, 'w') as f:
        f.write('\n'.join(flat) + '\n')
    print(f'\n--- {out_img} ---')
    print(f'wrote {listfile}: {len(flat)} entries')

    base = open(BASE_IMG, 'rb').read()
    old_rs = struct.unpack('<I', base[OFF_RAMDISK_SIZE:OFF_RAMDISK_SIZE + 4])[0]
    base_rd = '/tmp/base_ramdisk_noload.bin'
    with open(base_rd, 'wb') as f:
        f.write(base[PAGE:PAGE + old_rs])

    new_rd = f'/tmp/twrp_ramdisk_{len(flat)}.bin'
    rc = repack_ramdisk.main(['repack_ramdisk', base_rd, new_rd,
                              '--write', 'lib/modules/6.18/modules.load.recovery',
                              listfile,
                              '--write', 'system/etc/recovery.fstab', FSTAB_SRC])
    if rc != 0:
        sys.exit('repack_ramdisk failed')

    pack(base, new_rd, out_img)


def build():
    flat, missing = report()
    if missing:
        sys.exit(f'FATAL: {len(missing)} entries unresolvable; refusing to build')

    listed = set(flat)
    flats = flat_modules()
    extras = [f for f in flats if f not in listed]

    build_variant([], OUT_IMG)
    if extras:
        build_variant(extras, OUT_IMG_FULL)


def pack(base, ramdisk_path, out):
    rd = open(ramdisk_path, 'rb').read()
    rd_size = len(rd)
    rd_end = PAGE + (rd_size + PAGE - 1) // PAGE * PAGE
    if rd_end + FOOTER_SIZE > PARTITION_SIZE:
        sys.exit(f'FATAL: ramdisk end {rd_end} leaves no room for the footer')

    header = bytearray(base[:PAGE])
    assert header[:8] == b'ANDROID!', header[:8]
    struct.pack_into('<I', header, OFF_KERNEL_SIZE, 0)
    struct.pack_into('<I', header, OFF_RAMDISK_SIZE, rd_size)
    struct.pack_into('<I', header, OFF_OS_VERSION, 0)
    struct.pack_into('<I', header, OFF_HEADER_SIZE, HEADER_SIZE)
    struct.pack_into('<I', header, 40, 4)

    footer = bytearray(base[-FOOTER_SIZE:])
    if footer[:4] != b'AVBf':
        sys.exit(f'FATAL: base image has no AVB footer (tail={bytes(footer[:4])!r})')
    ver_major, ver_minor = struct.unpack('>II', footer[4:12])
    old_orig, old_off, vb_size = struct.unpack('>QQQ', footer[OFF_F_ORIG:OFF_F_VBMETA_SIZE + 8])
    print(f'\nAVB footer (base): ver {ver_major}.{ver_minor} '
          f'orig={old_orig} vbmeta_off={old_off} vbmeta_size={vb_size}')

    # The base image carries a vbmeta blob immediately after its ramdisk. It
    # is part of the image the device already boots, so it must be carried
    # over byte for byte - zeroing this region is a regression, not a cleanup.
    base_rd_end = PAGE + (struct.unpack('<I', base[OFF_RAMDISK_SIZE:OFF_RAMDISK_SIZE + 4])[0]
                          + PAGE - 1) // PAGE * PAGE
    if old_off != base_rd_end:
        sys.exit('FATAL: unsupported base trailer placement')
    padded_tail = base[base_rd_end:PARTITION_SIZE - FOOTER_SIZE]
    # Carry all meaningful bytes but regenerate partition zero padding; the
    # ramdisk may grow when a device runtime is added.
    tail_length = max(vb_size, len(padded_tail.rstrip(b'\x00')))
    tail = padded_tail[:tail_length]
    if rd_end + len(tail) > PARTITION_SIZE - FOOTER_SIZE:
        sys.exit('FATAL: packed payload exceeds recovery partition')
    nz = sum(1 for b in tail if b)
    print(f'base tail {base_rd_end}..{PARTITION_SIZE - FOOTER_SIZE}: '
          f'{len(tail)} bytes, {nz} non-zero -> carried over verbatim')
    if rd_end != base_rd_end:
        print(f'  NOTE: ramdisk end moved {base_rd_end} -> {rd_end}, tail follows')

    struct.pack_into('>Q', footer, OFF_F_ORIG, rd_end)
    struct.pack_into('>Q', footer, OFF_F_VBMETA_OFF, rd_end)
    # vbmeta_size is left untouched: it describes the blob that follows the
    # image and the base image already boots with it.

    image = bytearray(PARTITION_SIZE)
    image[:PAGE] = header
    image[PAGE:PAGE + rd_size] = rd
    image[rd_end:rd_end + len(tail)] = tail
    image[PARTITION_SIZE - FOOTER_SIZE:] = footer

    if rd_end + len(tail) > PARTITION_SIZE - FOOTER_SIZE:
        sys.exit('FATAL: carried-over tail overruns the footer')

    with open(out, 'wb') as f:
        f.write(bytes(image))

    import hashlib
    print(f'packed {out}')
    print(f'  size            : {PARTITION_SIZE}')
    print(f'  ramdisk_size    : {rd_size} (page end {rd_end})')
    print(f'  avb orig/offset : {rd_end} / {rd_end}')
    print(f'  md5             : {hashlib.md5(bytes(image)).hexdigest()}')


def main(argv):
    if len(argv) > 1 and argv[1] == 'build':
        sys.exit('Legacy first-stage-list builds are retired; use compile_recovery.sh and verify_source_recovery.py')
    else:
        report()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))