#!/usr/bin/env python3
"""Dump the boot-image header (v3/v4 layout) and the AVB footer of an image."""
import struct
import sys

PAGE = 4096


def header(d):
    magic = d[:8]
    kernel_size, ramdisk_size, os_version, header_size = struct.unpack('<IIII', d[8:24])
    reserved = struct.unpack('<IIII', d[24:40])
    header_version = struct.unpack('<I', d[40:44])[0]
    cmdline = d[44:44 + 1536].rstrip(b'\x00')
    return dict(magic=magic, kernel_size=kernel_size, ramdisk_size=ramdisk_size,
                os_version=os_version, header_size=header_size, reserved=reserved,
                header_version=header_version, cmdline=cmdline)


def footer(d):
    tail = d[-64:]
    if tail[:4] != b'AVBf':
        return None
    ver_major, ver_minor = struct.unpack('<II', tail[4:12])
    orig, vb_off, vb_size = struct.unpack('<QQQ', tail[12:36])
    return dict(ver_major=ver_major, ver_minor=ver_minor,
                original_image_size=orig, vbmeta_offset=vb_off, vbmeta_size=vb_size)


for p in sys.argv[1:]:
    d = open(p, 'rb').read()
    h = header(d)
    print(f'== {p}  ({len(d)} bytes)')
    print(f'   magic={h["magic"]!r} kernel_size={h["kernel_size"]} '
          f'ramdisk_size={h["ramdisk_size"]} os_version={h["os_version"]} '
          f'header_size={h["header_size"]} hv={h["header_version"]}')
    print(f'   reserved={h["reserved"]} cmdline={h["cmdline"][:60]!r}')
    print(f'   ramdisk magic @{PAGE}: {d[PAGE:PAGE + 4].hex()}')
    end = PAGE + (h['ramdisk_size'] + PAGE - 1) // PAGE * PAGE
    print(f'   ramdisk end (page aligned) = {end}')
    f = footer(d)
    print(f'   AVB footer: {f}')

    # how many non-zero bytes after the ramdisk up to the footer region
    tail_start = len(d) - 64
    nz = sum(1 for b in d[end:tail_start] if b)
    print(f'   non-zero bytes between ramdisk end and footer: {nz}')