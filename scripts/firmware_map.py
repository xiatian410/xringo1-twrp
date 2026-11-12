#!/usr/bin/env python3
"""Map an OTA `payload.bin` completely: every partition, its size, its ops.

This is the "where is X in the firmware" tool.  It prints, for each partition,
the number of install operations, the data range those operations occupy in
payload.bin (absolute file offsets), and which compression each op uses - so
you know both *where* the bytes are and *what you have to do* to get them out.

The manifest itself is protobuf (DeltaArchiveManifest); the field numbers used
here were verified against the OS4.0.0.19 dijun payload:

    payload header   0 magic "CrAU", 4 u64 version, 12 u64 manifest_size,
                     20 u32 metadata_signature_size, 24 manifest bytes
    manifest         13 PartitionUpdate, 15 DynamicPartitionMetadata
    PartitionUpdate  1 name, 7 new_partition_info, 8 operations
    PartitionInfo    1 size
    InstallOperation 1 type, 2 data_offset, 3 data_length, 6 dst_extents
    DynamicPartitionMetadata 1 groups
    DynamicPartitionGroup    1 name, 2 size, 3 partition_names

All integers big endian; data offsets are absolute from the start of payload.bin.

Usage:
    python3 -I firmware_map.py <ota.zip>            # full map
    python3 -I firmware_map.py <ota.zip> boot       # detail for one partition
"""
import struct
import sys
import zipfile

OP_NAMES = {0: "REPLACE", 1: "REPLACE_BZ", 8: "REPLACE_XZ"}
BLOCK = 4096


def rv(buf, pos):
    result = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def fields(buf, start, end):
    pos = start
    while pos < end:
        tag, pos = rv(buf, pos)
        f, w = tag >> 3, tag & 7
        if w == 0:
            v, pos = rv(buf, pos)
        elif w == 2:
            ln, pos = rv(buf, pos)
            v = (pos, pos + ln)
            pos += ln
        elif w == 5:
            v = buf[pos:pos + 4]
            pos += 4
        elif w == 1:
            v = buf[pos:pos + 8]
            pos += 8
        else:
            raise ValueError(f"bad wire type {w} at {pos}")
        yield f, w, v


def load(zippath):
    with zipfile.ZipFile(zippath) as z, z.open("payload.bin") as f:
        head = f.read(24)
        magic, version, mlen, meta_sig = struct.unpack(">4sQQI", head)
        assert magic == b"CrAU", magic
        manifest = f.read(mlen)
    return version, mlen, meta_sig, manifest, 24 + mlen + meta_sig


def partitions(manifest):
    out = []
    for f, w, v in fields(manifest, 0, len(manifest)):
        if f != 13 or w != 2:
            continue
        name = size = None
        ops = []
        for f2, w2, v2 in fields(manifest, *v):
            if f2 == 1 and w2 == 2:
                name = manifest[v2[0]:v2[1]].decode()
            elif f2 == 7 and w2 == 2:
                for f3, w3, v3 in fields(manifest, *v2):
                    if f3 == 1 and w3 == 0:
                        size = v3
            elif f2 == 8 and w2 == 2:
                op = {}
                for f3, w3, v3 in fields(manifest, *v2):
                    if w3 == 0:
                        op[f3] = v3
                ops.append(op)
        if name:
            out.append({"name": name, "size": size, "ops": ops})
    return out


def groups(manifest):
    out = []
    for f, w, v in fields(manifest, 0, len(manifest)):
        if f != 15 or w != 2:
            continue
        for f2, w2, v2 in fields(manifest, *v):
            if f2 == 1 and w2 == 2:          # groups
                g = {"name": None, "size": None, "parts": []}
                for f3, w3, v3 in fields(manifest, *v2):
                    if f3 == 1 and w3 == 2:
                        g["name"] = manifest[v3[0]:v3[1]].decode()
                    elif f3 == 2 and w3 == 0:
                        g["size"] = v3
                    elif f3 == 3 and w3 == 2:
                        g["parts"].append(manifest[v3[0]:v3[1]].decode())
                out.append(g)
    return out


def main(argv):
    zippath = argv[1]
    want = argv[2] if len(argv) > 2 else None
    version, mlen, meta_sig, manifest, data_base = load(zippath)
    parts = partitions(manifest)
    grp = groups(manifest)

    print(f"payload.bin: version={version} manifest={mlen}B meta_sig={meta_sig}B")
    print(f"data section starts at payload offset {data_base} (0x{data_base:x})\n")

    for g in grp:
        print(f"dynamic group '{g['name']}' size={g['size']} "
              f"({g['size'] / 1073741824:.2f} GiB), {len(g['parts'])} partitions")
        print("   " + " ".join(g["parts"]) + "\n")

    if want:
        for p in parts:
            if p["name"] != want:
                continue
            print(f"[{p['name']}] size={p['size']} ops={len(p['ops'])}")
            for i, op in enumerate(p["ops"][:40]):
                t = OP_NAMES.get(op.get(1, 0), op.get(1))
                off, ln = op.get(2, 0), op.get(3, 0)
                print(f"  op{i:<3} {t:<11} payload@{off} (+{ln}B)  "
                      f"absolute@{data_base + off}")
            if len(p["ops"]) > 40:
                print(f"  ... {len(p['ops']) - 40} more ops")
        return 0

    print(f"{'partition':<22}{'size':>12}  {'ops':>4}  {'payload range':>22}  types")
    for p in sorted(parts, key=lambda x: -(x["size"] or 0)):
        if not p["ops"]:
            print(f"{p['name']:<22}{p['size'] or 0:>12}  {0:>4}  {'-':>22}")
            continue
        lo = min(op.get(2, 0) for op in p["ops"])
        hi = max(op.get(2, 0) + op.get(3, 0) for op in p["ops"])
        types = sorted({OP_NAMES.get(op.get(1, 0), str(op.get(1))) for op in p["ops"]})
        print(f"{p['name']:<22}{p['size'] or 0:>12}  {len(p['ops']):>4}  "
              f"{f'{lo}..{hi}':>22}  {','.join(types)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
