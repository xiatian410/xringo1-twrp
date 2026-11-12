#!/usr/bin/env python3
"""Analyse the flat 6.18 dlkm module set: touch stack, deps, and what the
vendor_boot 139 already provide."""
import os
import sys

DLKM = '/tmp/base/files/lib/modules/6.18'
VB = '/tmp/vb_modules.load.recovery'

kos = sorted(f for f in os.listdir(DLKM) if f.endswith('.ko'))
print('dlkm flat modules:', len(kos))

print('\n--- touch / shub / input-ish modules present in dlkm set ---')
for f in kos:
    if any(k in f for k in ('touch', 'shub', 'synaptics', 'nt36', 'goodix', 'fts', 'input',
                            'spi', 'tp_', 'o2s')):
        print('   ', f, os.path.getsize(os.path.join(DLKM, f)))

# vendor_boot set (basenames)
vb = set()
for line in open(VB):
    line = line.strip()
    if line:
        vb.add(line.rsplit('/', 1)[-1])
print('\nvendor_boot 139 basenames with touch/shub/input:',
      sorted(x for x in vb if any(k in x for k in ('touch', 'shub', 'synaptics', 'nt36', 'input'))))

# modules.dep of the dlkm set
dep = {}
for line in open(os.path.join(DLKM, 'modules.dep')):
    lhs, sep, rhs = line.strip().partition(':')
    if not sep:
        continue
    dep[lhs.strip()] = [d for d in rhs.split()]

def closure(root):
    out, stack = [], [root]
    while stack:
        m = stack.pop(0)
        if m in out:
            continue
        out.append(m)
        for d in dep.get(m, []):
            if d not in out:
                stack.append(d)
    return out

print('\n--- dependency closure for candidate touch roots ---')
for root in ('xiaomi_touch_dijun.ko', 'synaptics_tcm2.ko', 'shub_boot_prepare.ko',
             'shub_ipc_drv.ko', 'shub_app_router.ko', 'touch_boost.ko'):
    if root in dep or os.path.exists(os.path.join(DLKM, root)):
        c = closure(root)
        print(f'{root}: {len(c)} -> {c}')
    else:
        print(f'{root}: ABSENT from dlkm set')

# softdep references that could pull things in
print('\n--- modules.softdep lines mentioning touch/shub ---')
for line in open(os.path.join(DLKM, 'modules.softdep')):
    if any(k in line for k in ('touch', 'shub', 'synaptics')):
        print('   ', line.rstrip())

print('\n--- dlkm modules NOT provided by vendor_boot 139 (by basename) ---')
only = [f for f in kos if f not in vb]
print(len(only), 'of', len(kos))
print(sorted(only))