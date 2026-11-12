"""Parse payload.bin manifest from inside the OTA zip (streamed) and list partitions.

DeltaArchiveManifest field 13 = repeated PartitionUpdate;
PartitionUpdate field 1 = partition_name, field 7 = new_partition_info (PartitionInfo),
PartitionInfo field 1 = size (varint), field 2 = hash (bytes).
"""
import io
import struct
import sys
import zipfile


def read_varint(buf, pos):
    result = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7


def parse_fields(buf, start, end):
    """Yield (field_number, wire_type, value) for a message body [start, end)."""
    pos = start
    while pos < end:
        tag, pos = read_varint(buf, pos)
        field, wire = tag >> 3, tag & 7
        if wire == 0:  # varint
            val, pos = read_varint(buf, pos)
        elif wire == 2:  # length-delimited
            ln, pos = read_varint(buf, pos)
            val = (pos, pos + ln)
            pos += ln
        elif wire == 5:  # 32-bit
            val = buf[pos:pos + 4]
            pos += 4
        elif wire == 1:  # 64-bit
            val = buf[pos:pos + 8]
            pos += 8
        else:
            raise ValueError(f"unexpected wire type {wire} at {pos}")
        yield field, wire, val


def main(zippath):
    with zipfile.ZipFile(zippath) as z:
        with z.open("payload.bin") as f:
            head = f.read(24)
            magic, version, manifest_len, sig_len = struct.unpack(">4sQQI", head)
            assert magic == b"CrAU", magic
            manifest = f.read(manifest_len)

    parts = []
    for field, wire, val in parse_fields(manifest, 0, len(manifest)):
        if field == 13 and wire == 2:
            s, e = val
            name = size = None
            try:
                for f2, w2, v2 in parse_fields(manifest, s, e):
                    if f2 == 1 and w2 == 2:
                        a, b = v2
                        name = manifest[a:b].decode()
                    elif f2 == 7 and w2 == 2:  # new_partition_info
                        a, b = v2
                        try:
                            for f3, w3, v3 in parse_fields(manifest, a, b):
                                if f3 == 1 and w3 == 0:
                                    size = v3
                        except ValueError:
                            pass
            except ValueError:
                pass
            if name:
                parts.append((name, size))

    print(f"payload version={version} manifest_len={manifest_len} sig_len={sig_len}")
    print(f"{len(parts)} partitions:")
    for name, size in parts:
        print(f"  {name:<20} {size/1024/1024:10.2f} MB" if size else f"  {name:<20} (no size)")


if __name__ == "__main__":
    main(sys.argv[1])
