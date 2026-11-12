#!/usr/bin/env python3
"""Sanity-check the dual-kernel module layout of a device tree.

Checks, per /lib/modules/<major>.<minor>/ directory:
  * every module's vermagic starts with that directory's <major>.<minor>
  * every modules.dep key and value names a file we actually ship there
  * every module in the directory has a modules.dep entry
  * TW_LOAD_VENDOR_MODULES / TWRP_TOUCH_MODULES name modules that exist in at
    least one version dir or one prebuilt/<variant>/vendor_boot_modules/<ver>/

modules.softdep is only checked for its owner, not its references: the vendor
files legitimately mention modules that live in vendor_dlkm
("softdep xring_audio pre: xring_smartpa"), and libmodprobe treats a missing
softdep target as a no-op.  Dangling entries in modules.dep, by contrast, mean
a module we ship cannot resolve a dependency we claim it has.

The shared modules.dep also carries dependency lines for modules that only some
variants ship (the jinghu/violin touch drivers).  Those are accepted as long as
the module exists in some prebuilt/<variant>/vendor_boot_modules/<ver>/, since
the prebuilt package copies only the current variant's *.ko.

Usage: python3 -I verify_tree.py <tree_root>
Exit status 1 if anything is wrong.
"""
import pathlib
import re
import struct
import sys


def section(blob, wanted):
    """Return the bytes of a named ELF section (ELF64 little endian), or None."""
    if blob[:4] != b"\x7fELF":
        return None
    e_shoff = struct.unpack_from("<Q", blob, 0x28)[0]
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", blob, 0x3A)
    secs = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        (_, _, _, _, sh_offset, sh_size, _, _, _, _) = struct.unpack_from("<IIQQQQIIQQ", blob, off)
        secs.append((sh_offset, sh_size))
    str_off, str_size = secs[e_shstrndx]
    strtab = blob[str_off:str_off + str_size]
    for i, (off, size) in enumerate(secs):
        n_off = struct.unpack_from("<I", blob, e_shoff + i * e_shentsize)[0]
        end = strtab.index(b"\0", n_off)
        if strtab[n_off:end].decode() == wanted:
            return blob[off:off + size]
    return None


def vermagic(blob):
    """The exact vermagic string from .modinfo, or '?' when absent.

    A fuzzy scan over the whole ELF file is wrong: unrelated .rodata strings
    ("1.2", "5.2", "0.0") match a version-looking regex and produce bogus
    mismatches.  .modinfo holds one NUL-terminated "vermagic=<version> ...".
    """
    mi = section(blob, ".modinfo")
    if not mi:
        return "?"
    for entry in mi.split(b"\0"):
        if entry.startswith(b"vermagic="):
            return entry[len(b"vermagic="):].decode("latin-1")
    return "?"


def canon(name):
    return name[:-3].replace("-", "_") if name.endswith(".ko") else name.replace("-", "_")


def requested_modules(root):
    s = (root / "BoardConfig.mk").read_text()
    i = s.index("TW_LOAD_VENDOR_MODULES :=")
    j = s.index("TW_LOAD_VENDOR_MODULES_EXCLUDE_GKI", i)
    names = re.findall(r"[A-Za-z0-9_.\-]+\.ko", s[i:j])
    # $(TWRP_TOUCH_MODULES) is per product; read it from the variant makefiles
    for mk in root.glob("twrp_*.mk"):
        m = re.search(r"TWRP_TOUCH_MODULES\s*:=\s*(.+)", mk.read_text())
        if m:
            names += re.findall(r"[A-Za-z0-9_.\-]+\.ko", m.group(1))
    return list(dict.fromkeys(names))


def main(root):
    root = pathlib.Path(root)
    moddir = root / "recovery/root/lib/modules"
    versions = sorted(p for p in moddir.iterdir() if p.is_dir())

    problems = []
    available = set()

    for d in versions:
        ver = d.name
        kos = {p.name for p in d.glob("*.ko")}
        available |= kos

        bad_magic = []
        for p in sorted(d.glob("*.ko")):
            got = vermagic(p.read_bytes())
            if not got.startswith(ver + "."):
                bad_magic.append((p.name, got))
        if bad_magic:
            problems.append(f"{ver}: {len(bad_magic)} modules with foreign vermagic, e.g. {bad_magic[:3]}")

        dep = d / "modules.dep"
        entries = {}
        if dep.exists():
            for ln in dep.read_text().splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    entries[k.strip()] = v.split()

        # names shipped by *some* variant for this version
        variant_kos = set()
        for vdir in (root / "prebuilt").glob(f"*/vendor_boot_modules/{ver}"):
            variant_kos |= {p.name for p in vdir.glob("*.ko")}
        known = kos | variant_kos

        undepended = sorted(kos - set(entries))
        if undepended:
            problems.append(f"{ver}: {len(undepended)} modules without modules.dep entry: {undepended[:5]}")
        dangling = sorted({x for v in entries.values() for x in v if x not in known})
        if dangling:
            problems.append(f"{ver}: modules.dep references unknown files: {dangling[:5]}")
        unknown_keys = sorted(k for k in entries if k not in known)
        if unknown_keys:
            problems.append(f"{ver}: modules.dep has entries for unknown modules: {unknown_keys[:5]}")

        # softdep lines naming a module we do not ship are a no-op for
        # libmodprobe (it only acts on modules it loads), so only count them.
        sd = d / "modules.softdep"
        foreign_owners = 0
        if sd.exists():
            by_canon = {canon(f) for f in kos}
            for ln in sd.read_text().splitlines():
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                toks = ln.replace("pre:", "pre: ").replace("post:", "post: ").split()
                if len(toks) < 2 or canon(toks[1]) not in by_canon:
                    foreign_owners += 1

        print(f"{ver}: {len(kos)} modules, {len(entries)} dep entries, "
              f"{len(sd.read_text().splitlines()) if sd.exists() else 0} softdep lines "
              f"({foreign_owners} for modules not shipped - harmless)")

    for vdir in sorted((root / "prebuilt").glob("*/vendor_boot_modules/*")):
        available |= {p.name for p in vdir.glob("*.ko")}

    req = requested_modules(root)
    absent = [r for r in req if r not in available]
    if absent:
        problems.append(f"TW_LOAD_VENDOR_MODULES names in no version dir: {absent}")
    print(f"TW_LOAD_VENDOR_MODULES: {len(req)} unique names")

    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
