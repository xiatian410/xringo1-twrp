#!/usr/bin/env python3
"""Derive modules.dep / modules.softdep from the firmware's own depmod output.

Gen-style regeneration from `.modinfo` is lossy: `softdep=` in a module's
modinfo carries only ONE pre:/post: list, while the firmware's
modules.softdep has several lines per owner (xring_thermal, xring_drm,
xring_i2c, ... each appear 2-5 times).  Regenerating therefore silently drops
load-ordering constraints.  The firmware files are already the authoritative
output of depmod for exactly these module builds, so filter and re-path those
instead of recomputing.

vendor_boot's /lib/modules/<ver>/modules.dep uses directory-relative paths
("extra/xring-modules/.../x.ko") and vendor_dlkm's uses absolute paths
("/vendor/lib/modules/x.ko").  Inside the recovery ramdisk both live flat in
/lib/modules/<ver>/, so every entry is rewritten to a bare filename and any
edge pointing at a module we do not ship is dropped.

Usage:
    python3 -I build_moddeps.py <modules_dir> <ref_dep:ref_softdep> ...

Each reference is given as "path/to/modules.dep" (softdep is looked up next to
it) or "path/to/modules.dep:path/to/modules.softdep".
"""
import os
import sys


def read_dep(path):
    """-> {filename: [dep filenames]}, paths flattened to basenames."""
    graph = {}
    if not os.path.exists(path):
        return graph
    order = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, rest = line.split(":", 1)
        key = os.path.basename(key.strip())
        graph[key] = [os.path.basename(p) for p in rest.split()]
        order.append(key)
    return graph


def read_softdep(path):
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def softdep_owner(line):
    toks = line.split()
    return toks[1] if len(toks) > 1 else ""


def normalize(ln):
    """Split a glued keyword off its first operand.

    The vendor file contains "softdep xr_dfx pre:dw_apb_rtc" (no space) as
    well as "softdep xr_ddr pre: xr_vote_mng"; both must parse the same way.
    """
    return " ".join(ln.replace("pre:", "pre: ").replace("post:", "post: ").split())


def softdep_refs(line):
    """Names referenced after pre:/post: (already suffix-free in this format).

    A pre:/post: list may hold several space-separated names until the next
    pre:/post: keyword ("softdep ps5169 post: redriver dwc3_msm"), so consume
    everything up to the next keyword, not just the first token.
    """
    toks = normalize(line).split()
    refs = []
    i = 0
    while i < len(toks):
        if toks[i] in ("pre:", "post:"):
            i += 1
            while i < len(toks) and toks[i] not in ("pre:", "post:"):
                refs.extend(toks[i].split(","))
                i += 1
        else:
            i += 1
    return [r for r in refs if r]


def canon(name):
    return name[:-3].replace("-", "_") if name.endswith(".ko") else name.replace("-", "_")


def main(argv):
    moddir = argv[1]
    present = {f for f in os.listdir(moddir) if f.endswith(".ko")}

    dep_tables, soft_all = [], []
    for spec in argv[2:]:
        dep_path, _, soft_path = spec.partition(":")
        dep_tables.append(read_dep(dep_path))
        soft_all.extend(read_softdep(soft_path or os.path.join(os.path.dirname(dep_path), "modules.softdep")))

    # merge graphs; first definition wins (vendor_boot before vendor_dlkm)
    graph = {}
    for t in dep_tables:
        for k, v in t.items():
            graph.setdefault(k, v)

    # transitive closure in load order, vendor order preserved
    def closure(m, stack=()):
        out = []
        for d in graph.get(m, []):
            if d in stack:
                continue
            for x in closure(d, stack + (m,)):
                if x not in out:
                    out.append(x)
            if d not in out:
                out.append(d)
        return out

    lines = []
    missing = []
    for m in sorted(present):
        if m not in graph:
            missing.append(m)
        deps = [d for d in closure(m) if d in present and d != m]
        lines.append(f"{m}: {' '.join(deps)}".rstrip() + (" " if deps else ""))

    # softdep: keep vendor ordering constraints, but only for modules we ship.
    # Ref lists are canonical (dash->underscore) names, so map back to files.
    # A line whose owner is absent is dropped; on a kept line, absent refs are
    # pruned rather than dropping the whole constraint (e.g. "ps5169 post:
    # redriver dwc3_msm" - dwc3_msm is not in the recovery module set, but the
    # redriver edge still matters).
    by_canon = {canon(f): f for f in present}
    kept, dropped, pruned = [], 0, 0
    for ln in soft_all:
        owner = softdep_owner(ln)
        if not owner or by_canon.get(owner) is None:
            dropped += 1
            continue
        refs = softdep_refs(ln)
        keep_refs = [r for r in refs if by_canon.get(canon(r)) is not None]
        if len(keep_refs) != len(refs):
            pruned += 1
        if not keep_refs:
            dropped += 1
            continue
        # rebuild the line with keyword structure intact, pruned
        toks = normalize(ln).split()
        out, i = [toks[0], toks[1]], 2
        while i < len(toks):
            if toks[i] in ("pre:", "post:"):
                kw = toks[i]
                i += 1
                vals = []
                while i < len(toks) and toks[i] not in ("pre:", "post:"):
                    for v in toks[i].split(","):
                        if by_canon.get(canon(v)) is not None:
                            vals.append(v)
                    i += 1
                if vals:
                    out.append(kw)
                    out.append(" ".join(vals))
            else:
                i += 1
        new = " ".join(out)
        if new not in kept:
            kept.append(new)

    open(os.path.join(moddir, "modules.dep"), "w").write("\n".join(lines) + "\n")
    open(os.path.join(moddir, "modules.softdep"), "w").write("\n".join(kept) + "\n")

    print(f"{moddir}: {len(lines)} modules ({sum(1 for l in lines if l.split(':',1)[1].strip())} with deps), "
          f"{len(kept)} softdep lines ({dropped} dropped, {pruned} pruned)")
    if missing:
        print(f"  WARNING no reference dep entry for: {sorted(missing)}")


if __name__ == "__main__":
    main(sys.argv)
