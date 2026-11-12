#!/usr/bin/env python3
"""Debug: check what pack() computes for the tail region."""
import struct
import sys

PAGE = 4096
PARTITION_SIZE = 104857600
FOOTER_SIZE = 64

base = open('/root/AAA/xringo1-twrp/imgs/built/twrp-recovery-noload.img', 'rb').read()
rd_size = struct.unpack('<I', base[12:16])[0]
base_rd_end = PAGE + (rd_size + PAGE - 1) // PAGE * PAGE
print('base rd_size', rd_size, 'rd_end', base_rd_end)
tail = base[base_rd_end:PARTITION_SIZE - FOOTER_SIZE]
print('tail len', len(tail), 'nonzero', sum(1 for b in tail if b))
print('tail head', tail[:16])
print('base[rd_end:rd_end+16]', base[base_rd_end:base_rd_end + 16])

new = open('/root/AAA/xringo1-twrp/imgs/built/twrp-recovery-flatlist.img', 'rb').read()
n_rd = struct.unpack('<I', new[12:16])[0]
n_end = PAGE + (n_rd + PAGE - 1) // PAGE * PAGE
print('new rd_size', n_rd, 'rd_end', n_end)
print('new[n_end:n_end+16]', new[n_end:n_end + 16])
print('len(new)', len(new))