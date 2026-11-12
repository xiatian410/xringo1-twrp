#!/usr/bin/env python3
"""Legacy CLI using the checked full-payload extractor.

Data offsets are relative to the payload DATA section (after its header,
manifest and metadata signatures). Output is published only after matching
new_partition_info SHA-256. ZIP_STORED payload and full operations only.
Use acquire_firmware.py for metadata provenance and remote range acquisition.
Usage: extract_payload_partition.py ota.zip partition output.img
"""
from pathlib import Path
import struct
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from acquire_firmware import ROOT, payload_position, read_at, parse_manifest, extract_partition


def main(source, partition, output):
    output = Path(output).absolute()
    if not output.parent.resolve().is_relative_to(ROOT) or output.is_symlink():
        raise ValueError('output must be a regular file within the task workspace')
    if output.exists() and not output.is_file():
        raise ValueError('refusing nonregular output')
    if Path(source).resolve() == output.resolve():
        raise ValueError('input and output are identical')
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(source, 'rb') as f, zipfile.ZipFile(source) as archive:
        info = archive.getinfo('payload.bin')
        if info.compress_type != zipfile.ZIP_STORED:
            raise ValueError('payload must be ZIP_STORED')
        position = payload_position(f, info)
        magic, version, size, sig = struct.unpack('>4sQQI', read_at(f, position, 24))
        if magic != b'CrAU' or version != 2 or size > 32*1024**2:
            raise ValueError('unsupported payload header')
        parsed = parse_manifest(read_at(f, position + 24, size))
        print(extract_partition(f, position + 24 + size + sig, position + info.file_size,
                               parsed['block_size'], parsed['partitions'][partition], output))


if __name__ == '__main__':
    main(*sys.argv[1:])
