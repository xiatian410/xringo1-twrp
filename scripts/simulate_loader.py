#!/usr/bin/env python3
"""Static rehearsal of TWRP's KernelModuleLoader against a built ramdisk.

It reproduces, without a phone, the path selection that
`bootable/recovery/kernel_module_loader.cpp` performs at runtime:

    module_dirs = [ /lib/modules,
                    /lib/modules/<ro.kernel.version> ]        <- uname major.minor
    plus, unless TW_LOAD_VENDOR_MODULES_EXCLUDE_GKI,
                    /lib/modules/<ro.kernel.version>-gki

and then, for each candidate directory, the libmodprobe work:
`WriteModuleList()` filters TW_LOAD_VENDOR_MODULES down to files that exist in
that directory, `Modprobe` parses modules.dep / modules.softdep from it and
loads the listed modules in dependency order.

For each kernel release argument we print which directory wins, which requested
modules are found there, and whether every requested module resolves to a file
in some directory.  A module that exists in neither set is reported as absent -
that is normal, `WriteModuleList()` simply skips it.

Usage: python3 -I simulate_loader.py <ramdisk_root> <kernel_release> [...]
       e.g. python3 -I simulate_loader.py <root> 6.18.21-android17-5-... 6.6.77-...
"""
import os
import re
import sys


def canonical(name):
    """libmodprobe Modprobe::MakeCanonical(): basename, drop .ko, '-' -> '_'."""
    base = name.rsplit('/', 1)[-1]
    if base.endswith('.ko'):
        base = base[:-3]
    return base.replace('-', '_')


def load_requested(recovery_binary):
    """Pull the compiled-in TW_LOAD_VENDOR_MODULES string out of the binary."""
    import subprocess

    out = subprocess.run(['strings', '-a', recovery_binary],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.endswith('.ko') and 'synaptics_tcm2.ko' in line:
            return line.split()
    return []


def parse_dep(moddir):
    """canonical -> [dependency paths], as ParseDepCallback builds it."""
    deps = {}
    path = os.path.join(moddir, 'modules.dep')
    if not os.path.exists(path):
        return deps
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        lhs, sep, rhs = line.partition(':')
        if not sep:
            continue
        deps[canonical(lhs)] = [d for d in rhs.split()]
    return deps


def parse_softdep(moddir):
    """(module, dep, 'pre'|'post') triples, as ParseSoftdepCallback builds it."""
    rows = []
    path = os.path.join(moddir, 'modules.softdep')
    if not os.path.exists(path):
        return rows
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        args = line.split()
        if args[0] != 'softdep' or len(args) < 4:
            rows.append(('MALFORMED', line, ''))
            continue
        state = ''
        for tok in args[2:]:
            if tok in ('pre:', 'post:'):
                state = tok[:-1]
                continue
            rows.append((canonical(args[1]), canonical(tok), state))
    return rows


def simulate(root, release):
    major_minor = '.'.join(release.split('.')[:2])
    base = os.path.join(root, 'lib', 'modules')
    print(f'\n=== kernel release {release} -> ro.kernel.version={major_minor} ===')

    candidates = [base]
    if os.path.isdir(os.path.join(base, major_minor)):
        candidates.append(os.path.join(base, major_minor))
    gki = os.path.join(base, major_minor + '-gki')
    if os.path.isdir(gki):
        candidates.append(gki)

    requested = load_requested(os.path.join(root, 'system/bin/recovery'))
    print(f'TW_LOAD_VENDOR_MODULES entries: {len(requested)}')

    resolved = {}
    for d in candidates:
        kos = {f for f in os.listdir(d) if f.endswith('.ko')} if os.path.isdir(d) else set()
        print(f'  probe {d.replace(root, "<ramdisk>")}: {len(kos)} *.ko')
        if kos:
            resolved[d] = kos

    winner = None
    for d in candidates:
        if d in resolved:
            winner = d
            break
    if winner is None:
        print('  -> no module directory matched this kernel; nothing loads')
        return False

    kos = resolved[winner]
    wanted = [m for m in requested if m in kos]
    missing = [m for m in requested if m not in kos]
    print(f'  -> selected {winner.replace(root, "<ramdisk>")}')
    print(f'     requested present here : {len(wanted)}/{len(requested)}')
    if missing:
        print(f'     skipped (not in dir)   : {len(missing)} e.g. {missing[:5]}')

    deps = parse_dep(winner)
    soft = parse_softdep(winner)
    have = {canonical(f) for f in kos}

    dangling, unlisted = [], []
    for m in wanted:
        c = canonical(m)
        if c not in deps:
            unlisted.append(m)
            continue
        for d in deps[c]:
            if canonical(d) not in have:
                dangling.append((c, d))

    soft_bad = [(m, d, s) for (m, d, s) in soft
                if m not in have or (d not in have and d not in deps)]

    print(f'     modules.dep entries    : {len(deps)}')
    print(f'     modules.softdep entries: {len(soft)}  malformed={sum(1 for s in soft if s[0] == "MALFORMED")}')
    print(f'     dangling hard deps     : {len(dangling)} {dangling[:3]}')
    print(f'     requested w/o dep entry: {len(unlisted)} {unlisted[:3]}')
    print(f'     softdep refs unresolved: {len(soft_bad)} {soft_bad[:3]}')
    return not dangling and not unlisted


def main(argv):
    root = argv[1]
    ok = True
    for rel in argv[2:]:
        ok &= simulate(root, rel)
    print('\nRESULT:', 'OK' if ok else 'PROBLEMS FOUND')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
