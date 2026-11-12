#!/usr/bin/env python3
"""Filter and re-pack an Android ramdisk (lz4-legacy / gzip / plain cpio).

Editing a ramdisk by extracting to a directory and re-running cpio loses the
original entry order, uid/gid and the exact padding that the recovery image
build depends on.  This script instead parses the original cpio, drops the
entries named on the command line, and re-emits every surviving entry with its
original header fields, so the result differs from the input in exactly the
ways asked for.

Usage:
    python3 -I repack_ramdisk.py <in.ramdisk> <out.ramdisk> [--drop NAME ...]

NAME matches a cpio path either exactly or as a directory prefix (so dropping
"lib/modules/6.6/modules.load.recovery" removes that one file).
"""
import gzip
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lz4legacy import decompress as unlz4_legacy  # noqa: E402

LZ4_LEGACY_MAGIC = b"\x02\x21\x4c\x18"
GZIP_MAGIC = b"\x1f\x8b"


def parse_cpio(blob):
    """-> [(name, mode, uid, gid, nlink, mtime, filesize, devmajor, devminor,
           rdevmajor, rdevminor, data)] preserving header order."""
    out = []
    pos = 0
    while pos + 110 <= len(blob):
        if blob[pos:pos + 6] not in (b"070701", b"070702"):
            if blob[pos] == 0:
                pos += 1
                continue
            break

        def hd(i):
            return int(blob[pos + 6 + 8 * i: pos + 6 + 8 * (i + 1)], 16)

        mode, uid, gid, nlink, mtime = hd(1), hd(2), hd(3), hd(4), hd(5)
        filesize, devmajor, devminor = hd(6), hd(7), hd(8)
        rdevmajor, rdevminor, namesize = hd(9), hd(10), hd(11)
        name = blob[pos + 110: pos + 110 + namesize - 1].decode(errors="replace")
        data_off = (pos + 110 + namesize + 3) & ~3
        data = blob[data_off:data_off + filesize]
        pos = (data_off + filesize + 3) & ~3
        out.append((name, mode, uid, gid, nlink, mtime, filesize,
                    devmajor, devminor, rdevmajor, rdevminor, data))
        if name == "TRAILER!!!":
            break
    return out


def emit_cpio(entries):
    buf = bytearray()
    ino = 0
    for (name, mode, uid, gid, nlink, mtime, filesize,
         devmajor, devminor, rdevmajor, rdevminor, data) in entries:
        ino += 1
        name_b = name.encode() + b"\x00"
        # newc header: magic + 13 fields of 8 hex digits (110 bytes total)
        fields = [ino, mode, uid, gid, nlink, mtime, len(data),
                  devmajor, devminor, rdevmajor, rdevminor, len(name_b), 0]
        buf += b"070701" + b"".join(b"%08x" % f for f in fields)
        buf += name_b
        buf += b"\x00" * ((4 - len(buf) % 4) % 4)
        buf += data
        buf += b"\x00" * ((4 - len(buf) % 4) % 4)
    # cpio needs the archive padded to 512 bytes
    buf += b"\x00" * ((512 - len(buf) % 512) % 512)
    return bytes(buf)


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    src, dst = argv[1], argv[2]
    drop = []
    writes = {}          # cpio path -> local file to take the contents from
    i = 3
    while i < len(argv):
        if argv[i] == "--drop" and i + 1 < len(argv):
            drop.append(argv[i + 1].lstrip("/"))
            i += 2
        elif argv[i] == "--write" and i + 2 < len(argv):
            writes[argv[i + 1].lstrip("/")] = argv[i + 2]
            i += 3
        else:
            sys.exit(f"unknown argument {argv[i]}")

    raw = open(src, "rb").read()
    if raw[:4] == LZ4_LEGACY_MAGIC:
        cpio, how = unlz4_legacy(raw), "lz4-legacy"
    elif raw[:2] == GZIP_MAGIC:
        cpio, how = gzip.decompress(raw), "gzip"
    else:
        cpio, how = raw, "none"
    print(f"read {src}: {how}, {len(raw)} -> {len(cpio)} bytes")

    entries = parse_cpio(cpio)

    def dropped(name):
        n = name.rstrip("/")
        return any(n == d or n.startswith(d + "/") for d in drop)

    kept = [e for e in entries if not dropped(e[0])]
    removed = [e[0] for e in entries if dropped(e[0])]
    print(f"entries: {len(entries)} -> {len(kept)}  (dropped {len(removed)})")
    for n in removed:
        print(f"  - {n}")
    if not removed and drop:
        print("  WARNING: nothing matched the --drop patterns")

    # --write replaces an existing entry's payload in place (mode/uid/mtime are
    # preserved), or appends a new one right before TRAILER.
    for path, srcfile in writes.items():
        payload = open(srcfile, "rb").read()
        for idx, e in enumerate(kept):
            if e[0].rstrip("/") == path:
                kept[idx] = e[:6] + (len(payload),) + e[7:11] + (payload,)
                print(f"replaced {path} with {len(payload)} B from {srcfile}")
                break
        else:
            ref = next((e for e in kept if e[0].rstrip("/") == os.path.dirname(path)), None)
            # A new payload is a regular file, never the parent directory type.
            mode = 0o100000 | (os.stat(srcfile).st_mode & 0o777)
            uid = ref[2] if ref else 0
            gid = ref[3] if ref else 0
            mtime = ref[5] if ref else 0
            trailer = next(i for i, e in enumerate(kept) if e[0] == "TRAILER!!!")
            kept.insert(trailer, (path, mode, uid, gid, 1, mtime, len(payload),
                                  0, 0, 0, 0, payload))
            print(f"added    {path} ({len(payload)} B) from {srcfile}")

    new_cpio = emit_cpio(kept)
    if how == "lz4-legacy":
        # `lz4 -l` produces the same legacy block format the stock ramdisk uses.
        env = dict(os.environ, LZ4="lz4")
        res = subprocess.run(["lz4", "-l", "-12", "-c", "-q"],
                             input=new_cpio, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=env)
        if res.returncode != 0:
            sys.exit(f"lz4 failed: {res.stderr.decode(errors='replace')}")
        packed = res.stdout
    elif how == "gzip":
        packed = gzip.compress(new_cpio, 9)
    else:
        packed = new_cpio
    with open(dst, "wb") as f:
        f.write(packed)
    print(f"wrote {dst}: {len(new_cpio)} -> {len(packed)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
