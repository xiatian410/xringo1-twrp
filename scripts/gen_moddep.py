#!/usr/bin/env python3
"""Build modules.dep / modules.softdep for a flat kernel-module directory.

TWRP's libmodprobe reads <dir>/modules.dep where entries are RELATIVE
filenames (e.g. "a.ko: b.ko").  Vendor vendor_dlkm ships absolute paths
(/vendor/lib/modules/x.ko) which cannot be reused inside a recovery
ramdisk, so regenerate from each module's own .modinfo fields.

Naming gotcha
-------------
A module's `depends=` field lists *canonical* module names, where the kernel
has already replaced '-' with '_'.  The file on disk keeps the dash:
"xring-drm.ko" has canonical name "xring_drm".  Naive
`dep.replace('-', '_') + '.ko'` therefore invents filenames that do not exist
and silently drops real dependency edges (41 of them in the 6.18 set: xring-drm,
xr-clk, sched-walt, perf-actuator, fsa4480-i2c, xr-pmic-spmi, ...).
resolve() below maps canonical -> actual filename.

Second gotcha: depmod writes the *transitive* closure into modules.dep, not the
direct depends= list (the vendor's 6.18 file lists 14 modules for xring_thermal,
whose .modinfo has 5).  transitive() reproduces that.

Still, prefer build_moddeps.py for firmware-sourced sets: softdep ordering
constraints can only be reproduced from the vendor's own modules.softdep,
because a module's modinfo carries at most one pre:/post: list.  This script is
the fallback for module sets with no vendor depmod output to copy from.

Usage: python3 -I gen_moddep.py <modules_dir> [--check]
"""
import os
import sys


def modinfo_strings(blob, key):
    out = []
    needle = key.encode() + b"="
    i = 0
    while True:
        i = blob.find(needle, i)
        if i < 0:
            return out
        j = blob.find(b"\x00", i)
        if j < 0:
            return out
        out.append(blob[i + len(needle):j].decode("utf-8", "replace"))
        i = j


def canonical(filename):
    """a-b.ko -> a_b (the name the kernel reports in depends=/softdep=)."""
    return filename[:-3].replace("-", "_")


def build_resolver(mods):
    """canonical module name -> real filename on disk."""
    table = {}
    for m in mods:
        table[canonical(m)] = m
    return table


def resolve(name, table):
    """Resolve a depends=/softdep= token to a filename, or None."""
    name = name.strip()
    if not name:
        return None
    if name.endswith(".ko"):
        name = name[:-3]
    if name in table:
        return table[name]
    # tolerate a token that already uses the on-disk spelling
    for cand in (name + ".ko", name.replace("_", "-") + ".ko"):
        if cand in table.values():
            return cand
    return None


def transitive(m, direct, order, stack=()):
    """depmod-style modules.dep entries are the full closure, in load order.

    Vendor reference (/lib/modules/6.18.../modules.dep) proves this: xring_thermal
    lists 14 modules while its .modinfo carries only 5 direct ones.
    """
    out = []
    for d in direct.get(m, []):
        if d in stack:
            continue  # cycle guard; keeps output finite
        if d not in order:
            order.add(d)
            out.extend(transitive(d, direct, order, stack + (m,)))
            out.append(d)
        elif d not in out:
            out.append(d)
    return out


def gen(moddir):
    mods = sorted(f for f in os.listdir(moddir) if f.endswith(".ko"))
    table = build_resolver(mods)
    direct, soft_lines = [], []
    blobs = {}

    for m in mods:
        blob = open(os.path.join(moddir, m), "rb").read()
        blobs[m] = blob
        deps = []
        for d in modinfo_strings(blob, "depends")[:1]:
            for tok in d.split(","):
                r = resolve(tok, table)
                if r and r != m and r not in deps:
                    deps.append(r)
        direct.append((m, deps))

    direct_map = dict(direct)
    dep_lines = []
    for m, deps in direct:
        closure = transitive(m, direct_map, set())
        # drop duplicates while keeping first-seen (load) order
        seen, ordered = set(), []
        for d in closure:
            if d not in seen and d != m:
                seen.add(d)
                ordered.append(d)
        dep_lines.append((m, ordered))

        # modules.softdep syntax (see vendor's own file):
        #   softdep <canonical owner, dashes -> underscores> pre: <name> <name>
        # Dependency tokens keep the on-disk spelling with dashes and carry NO
        # .ko suffix ("softdep xr_pmic_spmi pre: xr-spmi-controller").
        for s in modinfo_strings(blobs[m], "softdep")[:1]:
            toks = s.split()
            owner = canonical(m)

            def names(idx):
                out = []
                for p in toks[idx].split(","):
                    p = p.strip()
                    if p.endswith(".ko"):
                        p = p[:-3]
                    if p and resolve(p, table) and p not in out:
                        out.append(p)
                return out

            if "pre:" in toks:
                pre = names(toks.index("pre:") + 1)
                if pre:
                    soft_lines.append(f"softdep {owner} pre: {' '.join(pre)}")
            if "post:" in toks:
                post = names(toks.index("post:") + 1)
                if post:
                    soft_lines.append(f"softdep {owner} post: {' '.join(post)}")
    return dep_lines, soft_lines


def main(argv):
    moddir = argv[1]
    check = "--check" in argv
    dep_lines, soft_lines = gen(moddir)

    if check:
        existing = {}
        p = os.path.join(moddir, "modules.dep")
        if os.path.exists(p):
            for ln in open(p):
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    existing[k.strip()] = v.split()
        missing = 0
        for m, deps in dep_lines:
            got = existing.get(m)
            if got is None:
                continue
            lost = [d for d in deps if d not in got]
            if lost:
                missing += 1
                print(f"  {m}: missing {lost}")
        print(f"{moddir}: {len(dep_lines)} modules, {missing} files with lost deps")
        return

    dep_path = os.path.join(moddir, "modules.dep")
    with open(dep_path, "w") as f:
        for m, deps in dep_lines:
            f.write(f"{m}: {' '.join(deps)}".rstrip() + (" " if deps else "") + "\n")

    soft_path = os.path.join(moddir, "modules.softdep")
    with open(soft_path, "w") as f:
        for ln in soft_lines:
            f.write(ln + "\n")

    print(f"{moddir}: {len(dep_lines)} modules, "
          f"{sum(1 for _, d in dep_lines if d)} with deps, {len(soft_lines)} softdeps")


if __name__ == "__main__":
    main(sys.argv)
