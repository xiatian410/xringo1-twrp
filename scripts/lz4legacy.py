#!/usr/bin/env python3
"""Minimal LZ4 legacy-frame decoder (magic 0x184C2102).

Android ramdisks (boot/vendor_boot/recovery) use the *legacy* frame format,
which is not the same as the modern LZ4 frame (0x184D2204) that python-lz4
writes.  The container is trivial:

    magic  : u32 LE 0x184C2102
    repeat : u32 LE size
             if size & 0x80000000 -> next (size & 0x7fffffff) bytes are stored
             else                 -> next size bytes are one LZ4 block
    stop   : size == 0

Each LZ4 block is a sequence of (token, literals, offset, matchlen) tuples, per
the LZ4 block format spec (no dictionary, no checksums).

Usage:
    python3 -I lz4legacy.py <in.lz4> <out>
"""
import struct
import sys


def decode_block(src, dst):
    """Append one LZ4 block to bytearray dst."""
    i = 0
    n = len(src)
    while i < n:
        token = src[i]
        i += 1

        lit_len = token >> 4
        if lit_len == 15:
            while True:
                b = src[i]
                i += 1
                lit_len += b
                if b != 255:
                    break
        dst += src[i:i + lit_len]
        i += lit_len
        if i >= n:
            return  # last sequence has literals only

        offset = src[i] | (src[i + 1] << 8)
        i += 2
        if offset == 0:
            raise ValueError("zero offset in LZ4 block")

        match_len = token & 0x0F
        if match_len == 15:
            while True:
                b = src[i]
                i += 1
                match_len += b
                if b != 255:
                    break
        match_len += 4

        start = len(dst) - offset
        if start < 0:
            raise ValueError("match before start of output")
        # overlapping copies are legal and must be byte-wise
        for k in range(match_len):
            dst.append(dst[start + k])


def decompress(blob):
    if blob[:4] != b"\x02\x21\x4c\x18":
        raise ValueError("not an LZ4 legacy frame (magic %s)" % blob[:4].hex())
    pos = 4
    out = bytearray()
    while True:
        if pos + 4 > len(blob):
            break
        size = struct.unpack_from("<I", blob, pos)[0]
        pos += 4
        if size == 0:
            break
        if size & 0x80000000:
            n = size & 0x7FFFFFFF
            out += blob[pos:pos + n]
            pos += n
        else:
            decode_block(blob[pos:pos + size], out)
            pos += size
    return bytes(out)


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[-1])
        return 1
    data = decompress(open(argv[1], "rb").read())
    open(argv[2], "wb").write(data)
    print(f"{argv[1]} -> {argv[2]}: {len(data)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
