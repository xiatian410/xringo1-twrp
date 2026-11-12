"""Decompress an lz4-legacy / gzip / plain ramdisk and extract its cpio entries.

Android ramdisks here are LZ4 *legacy* frames (magic 0x184C2102), which the
`lz4` python package's block API cannot decode without an uncompressed_size
hint, and which is not a modern LZ4 frame either - so decoding is done by
lz4legacy.py, a self-contained block decoder with no dependencies.

Usage: python3 -I unpack_ramdisk.py <ramdisk> <outdir>
"""
import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lz4legacy import decompress as unlz4_legacy  # noqa: E402

LZ4_LEGACY_MAGIC = b"\x02\x21\x4c\x18"
GZIP_MAGIC = b"\x1f\x8b"


def cpio_entries(blob):
    """Yield (name, mode, filesize, data) for each newc entry; tolerate padding."""
    pos = 0
    while pos + 110 <= len(blob):
        if blob[pos:pos + 6] not in (b"070701", b"070702"):
            if blob[pos] == 0:
                pos += 1
                continue
            break

        def hd(i):
            return int(blob[pos + 6 + 8 * i: pos + 6 + 8 * (i + 1)], 16)

        mode, filesize, namesize = hd(1), hd(6), hd(11)
        name = blob[pos + 110: pos + 110 + namesize - 1].decode(errors="replace")
        data_off = (pos + 110 + namesize + 3) & ~3
        entry = blob[data_off:data_off + filesize]
        pos = (data_off + filesize + 3) & ~3
        yield name, mode, filesize, entry
        if name == "TRAILER!!!":
            # skip to the next archive fragment if concatenated
            pos = (pos + 511) & ~511 if pos % 512 else pos


def main(path, outdir):
    data = open(path, "rb").read()
    if data[:4] == LZ4_LEGACY_MAGIC:
        cpio, how = unlz4_legacy(data), "lz4-legacy"
    elif data[:2] == GZIP_MAGIC:
        cpio, how = gzip.decompress(data), "gzip"
    else:
        cpio, how = data, "none"

    os.makedirs(outdir, exist_ok=True)
    raw = os.path.join(outdir, "ramdisk.cpio")
    with open(raw, "wb") as f:
        f.write(cpio)
    print(f"{how}: {len(data)} -> {len(cpio)} bytes -> {raw}")

    count = 0
    for name, mode, filesize, entry in cpio_entries(cpio):
        kind = {0o100000: "f", 0o120000: "l", 0o040000: "d"}.get(mode & 0o170000, "?")
        if len(sys.argv) > 3:
            print(f"  {kind} {filesize:>9} {name}")
        if mode & 0o170000 == 0o100000 and filesize:
            dest = os.path.join(outdir, "files", name.lstrip("/").replace("/", os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(entry)
        count += 1
    print(f"{count} cpio entries extracted to {os.path.join(outdir, 'files')}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
