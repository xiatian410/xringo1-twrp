#!/usr/bin/env python3
"""Locate the AVB footer / vbmeta blob inside a recovery image."""
import sys

for p in sys.argv[1:]:
    d = open(p, 'rb').read()
    n = len(d)
    print(f'== {p} ({n} bytes)')
    idx = d.find(b'AVBf')
    print(f'   first AVBf at {idx} (from end: {n - idx if idx >= 0 else "n/a"})')
    while idx >= 0:
        print(f'     AVBf @ {idx}')
        idx = d.find(b'AVBf', idx + 1)
        if idx > n - 200:
            break
    # last 200 bytes hex-ish
    print('   tail 200 bytes repr:', d[-200:])
    print('   bytes before AVBf (if any) first 32:', d[max(0, (d.find(b"AVBf") - 32)):d.find(b"AVBf")].hex() if d.find(b"AVBf") > 0 else '')