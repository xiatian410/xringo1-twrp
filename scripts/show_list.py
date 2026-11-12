#!/usr/bin/env python3
"""Show the modules.load.recovery that ended up inside a built recovery image."""
import struct
import sys

sys.path.insert(0, '/root/AAA/xringo1-twrp/scripts')
from repack_ramdisk import parse_cpio  # noqa: E402
from lz4legacy import decompress  # noqa: E402

PAGE = 4096

img = sys.argv[1]
want = sys.argv[2] if len(sys.argv) > 2 else 'lib/modules/6.18/modules.load.recovery'

d = open(img, 'rb').read()
rd_size = struct.unpack('<I', d[12:16])[0]
ram = d[PAGE:PAGE + rd_size]
blob = decompress(ram) if ram[:4] == b'\x02\x21\x4c\x18' else ram
ents = {e[0]: e for e in parse_cpio(blob)}

e = ents.get(want)
if not e:
    print(f'{want}: NOT PRESENT')
    print('available module lists:', [n for n in ents if 'modules' in n and not n.endswith('.ko')])
    sys.exit(1)

lines = [x for x in e[11].decode().splitlines() if x.strip()]
print(f'{want}')
print(f'  mode=0o{e[1] & 0o7777:o} uid={e[2]} gid={e[3]} size={e[6]}')
print(f'  entries={len(lines)}')
print('  first 8:')
for x in lines[:8]:
    print('     ' + x)
print('  last 5:')
for x in lines[-5:]:
    print('     ' + x)

bad = [x for x in lines if '/' in x or not x.endswith('.ko')]
print(f'  entries that are not flat *.ko: {len(bad)} {bad[:5]}')

# cross-check against files really present in the same directory
siblings = {n.rsplit('/', 1)[-1] for n in ents
            if n.startswith('lib/modules/6.18/') and n.endswith('.ko')}
missing = [x for x in lines if x not in siblings]
print(f'  listed but absent from the ramdisk dir: {len(missing)} {missing[:5]}')
print(f'  .ko in dir not listed: {len(siblings - set(lines))}')