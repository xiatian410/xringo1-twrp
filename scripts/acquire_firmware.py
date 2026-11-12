#!/usr/bin/env python3
"""Read local/HTTP ZIP64 OTA metadata and extract verified full-payload partitions.

The protobuf fields follow system/update_engine/update_metadata.proto. Operation
data offsets are relative to the payload DATA section, not to payload.bin.
Only full-image REPLACE, REPLACE_BZ, REPLACE_XZ and ZERO/DISCARD are supported.
Every extracted partition must match the manifest's SHA-256 before publication.
No block devices, mounts, phones or signature-policy changes are used here.
"""
import argparse
import base64
import bz2
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import json
import lzma
from pathlib import Path
import re
import struct
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'firmware/samples'
CHUNK = 8 * 1024 * 1024
OP_NAMES = {0: 'REPLACE', 1: 'REPLACE_BZ', 6: 'ZERO', 7: 'DISCARD', 8: 'REPLACE_XZ'}


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()


class HttpRangeFile(io.RawIOBase):
    """Seekable pinned HTTP object; reject ignored/incorrect range responses."""
    def __init__(self, url):
        super().__init__()
        self.url = url
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=45) as r:
            self.length = int(r.headers['Content-Length'])
            self.etag = r.headers.get('ETag')
        if not self.etag or self.etag.startswith('W/'):
            raise ValueError('A strong ETag is required to pin HTTP reads')
        self.pos = 0
        self.cache = OrderedDict()
        self.bytes_fetched = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        pos = offset + (self.pos if whence == 1 else self.length if whence == 2 else 0)
        if whence not in (0, 1, 2) or pos < 0:
            raise ValueError('Invalid seek')
        self.pos = pos
        return pos

    def _chunk(self, start):
        if start in self.cache:
            self.cache.move_to_end(start)
            return self.cache[start]
        end = min(start + CHUNK, self.length) - 1
        headers = {'Range': f'bytes={start}-{end}', 'If-Match': self.etag,
                   'Accept-Encoding': 'identity'}
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(self.url, headers=headers), timeout=45) as r:
                    if (r.status != 206 or r.headers.get('Content-Range') !=
                            f'bytes {start}-{end}/{self.length}' or r.headers.get('ETag') != self.etag):
                        raise ValueError('HTTP object changed or server ignored range')
                    data = r.read(end - start + 2)
                    if len(data) != end - start + 1:
                        raise ValueError('Truncated or oversized HTTP range')
                break
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
        self.bytes_fetched += len(data)
        self.cache[start] = data
        while len(self.cache) > 4:
            self.cache.popitem(last=False)
        return data

    def read(self, size=-1):
        if size < 0:
            size = self.length - self.pos
        size = min(size, max(0, self.length - self.pos))
        if size > 128 * 1024 * 1024:
            raise ValueError('Unbounded HTTP read refused; use chunks')
        out = bytearray()
        while size:
            start = self.pos // CHUNK * CHUNK
            chunk = self._chunk(start)
            n = min(size, len(chunk) - (self.pos - start))
            out.extend(chunk[self.pos - start:self.pos - start + n])
            self.pos += n
            size -= n
        return bytes(out)


def fields(data):
    """Strict protobuf wire reader: preserve unknown fields, reject truncation."""
    pos = 0

    def varint():
        nonlocal pos
        result = 0
        for shift in range(0, 70, 7):
            if pos >= len(data):
                raise ValueError('Truncated protobuf varint')
            b = data[pos]
            pos += 1
            result |= (b & 127) << shift
            if not b & 128:
                if result >= 1 << 64:
                    raise ValueError('Protobuf integer overflow')
                return result
        raise ValueError('Overlong protobuf varint')

    while pos < len(data):
        tag = varint()
        number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError('Invalid protobuf field zero')
        if wire == 0:
            value = varint()
        elif wire in (1, 2, 5):
            n = varint() if wire == 2 else 8 if wire == 1 else 4
            if pos + n > len(data):
                raise ValueError('Truncated protobuf field')
            value = data[pos:pos + n]
            pos += n
        else:
            raise ValueError(f'Unsupported protobuf wire type {wire}')
        yield number, value


def parse_manifest(data):
    result = {'block_size': 4096, 'minor_version': 0, 'partitions': {}, 'groups': []}
    for number, value in fields(data):
        if number == 3:
            result['block_size'] = value
        elif number == 12:
            result['minor_version'] = value
        elif number == 13:
            part = {'operations': []}
            for field, v in fields(value):
                if field == 1:
                    part['name'] = v.decode()
                elif field == 7:
                    info = dict(fields(v))
                    part['size'] = info[1]
                    part['sha256'] = info[2].hex()
                elif field == 8:
                    op = {'extents': []}
                    for key, val in fields(v):
                        if key == 6:
                            extent = dict(fields(val))
                            op['extents'].append((extent[1], extent[2]))
                        elif key in (1, 2, 3, 7, 8):
                            op[key] = val
                    part['operations'].append(op)
            name = part['name']
            if not re.fullmatch(r'[a-zA-Z0-9_]+', name) or name in result['partitions']:
                raise ValueError('Unsafe or repeated partition name')
            if not 0 < part['size'] <= 16 * 1024**3 or len(part['sha256']) != 64:
                raise ValueError('Invalid partition size/hash')
            result['partitions'][name] = part
        elif number == 15:
            for field, v in fields(value):
                if field == 1:
                    group = {'partitions': []}
                    for key, val in fields(v):
                        if key == 1:
                            group['name'] = val.decode()
                        elif key == 2:
                            group['size'] = val
                        elif key == 3:
                            group['partitions'].append(val.decode())
                    result['groups'].append(group)
    bs = result['block_size']
    if bs < 512 or bs > 65536 or bs & (bs - 1):
        raise ValueError('Invalid block size')
    if result['minor_version'] != 0:
        raise ValueError('Delta OTA requires the exact source image; not supported')
    return result


def read_at(f, offset, size):
    f.seek(offset)
    data = f.read(size)
    if len(data) != size:
        raise ValueError('Truncated source')
    return data


def payload_position(f, info):
    if info.compress_type != zipfile.ZIP_STORED or info.flag_bits & 1:
        raise ValueError('Range extraction needs an unencrypted ZIP_STORED payload')
    header = read_at(f, info.header_offset, 30)
    if header[:4] != b'PK\x03\x04':
        raise ValueError('Bad ZIP local header')
    namesize, extra = struct.unpack_from('<HH', header, 26)
    return info.header_offset + 30 + namesize + extra


def extract_partition(f, base, payload_end, bs, part, output):
    if output.is_symlink() or output.with_suffix('.img.partial').is_symlink():
        raise ValueError('Refuse output symlink')
    if output.exists() and output.stat().st_size == part['size'] and sha256_file(output) == part['sha256']:
        return {'sha256': part['sha256'], 'size': part['size'], 'verified': True}
    spans = []
    for op in part['operations']:
        if op[1] not in OP_NAMES:
            raise ValueError(f'Unsupported operation {op[1]} in {part["name"]}')
        if not op['extents']:
            raise ValueError('Operation lacks destination extents')
        for start, blocks in op['extents']:
            if blocks <= 0 or start < 0 or (start + blocks) * bs > part['size']:
                raise ValueError('Invalid destination extent')
            spans.append((start * bs, (start + blocks) * bs))
    cursor = 0
    for start, end in sorted(spans):
        if start != cursor:
            raise ValueError('Overlapping or uncovered destination bytes')
        cursor = end
    if cursor != part['size']:
        raise ValueError('Incomplete partition coverage')
    partial = output.with_suffix('.img.partial')
    with partial.open('wb') as image:
        image.truncate(part['size'])
        for op in part['operations']:
            expected = sum(n * bs for _, n in op['extents'])
            if expected > 128 * 1024**2:
                raise ValueError('Oversized operation')
            if op[1] in (6, 7):
                if op.get(3, 0):
                    raise ValueError('Zero/discard operation unexpectedly has data')
                continue  # Newly truncated file is zero; final hash is mandatory.
            length, offset = op[3], base + op[2]
            if length <= 0 or offset < base or offset + length > payload_end:
                raise ValueError('Operation data outside payload')
            raw = read_at(f, offset, length)
            if 8 in op and hashlib.sha256(raw).digest() != op[8]:
                raise ValueError('Operation SHA-256 mismatch')
            if op[1] == 0:
                data = raw
            else:
                decompressor = bz2.BZ2Decompressor() if op[1] == 1 else lzma.LZMADecompressor()
                data = decompressor.decompress(raw, max_length=expected + 1)
                if not decompressor.eof or decompressor.unused_data:
                    raise ValueError('Incomplete, oversized or trailing compressed data')
            if len(data) != expected:
                raise ValueError('Operation output length differs from extents')
            pos = 0
            for start, blocks in op['extents']:
                image.seek(start * bs)
                n = blocks * bs
                image.write(data[pos:pos + n])
                pos += n
    if sha256_file(partial) != part['sha256']:
        raise ValueError(f'Partition SHA-256 mismatch: {part["name"]}')
    partial.replace(output)
    return {'sha256': part['sha256'], 'size': part['size'], 'verified': True}


def sources():
    rows = json.loads((ROOT / 'logs/firmware-source-head-20261111.json').read_text())
    return dict(zip(('os3-final', 'os3-initial', 'os2-final', 'os2-initial'),
                    [r['url'] for r in rows]),
                **{'os4-current': str(ROOT / 'dijun-ota_full-OS4.0.0.19.XODCNXM-user-17.0-aa6a58e947.zip'),
                   'os4-stable': 'https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS4.0.4.0.XODCNXM/dijun-ota_full-OS4.0.4.0.XODCNXM-user-17.0-b0ce732f48.zip'})


def acquire(sample, source, wanted):
    dest = SAMPLES / sample
    dest.mkdir(parents=True, exist_ok=True)
    remote = source.startswith('https://')
    f = HttpRangeFile(source) if remote else open(source, 'rb')
    try:
        with zipfile.ZipFile(f) as z:
            info = z.getinfo('payload.bin')
            position = payload_position(f, info)
            entries = []
            for name in ('META-INF/com/android/metadata', 'payload_properties.txt'):
                entry = z.getinfo(name)
                if entry.file_size > 1024 * 1024:
                    raise ValueError('Oversized OTA metadata')
                contents = z.read(name)  # zipfile verifies the metadata entry CRC.
                (dest / Path(name).name).write_bytes(contents)
                entries.append({'name': name, 'sha256': hashlib.sha256(contents).hexdigest()})
        head = read_at(f, position, 24)
        magic, version, length, signature_length = struct.unpack('>4sQQI', head)
        if magic != b'CrAU' or version != 2 or length > 64 * 1024**2:
            raise ValueError('Unsupported payload header')
        base = position + 24 + length + signature_length
        if base > position + info.file_size:
            raise ValueError('Metadata outside payload')
        manifest = read_at(f, position + 24, length)
        properties = dict(line.split('=', 1) for line in (dest / 'payload_properties.txt').read_text().splitlines() if '=' in line)
        metadata_digest = hashlib.sha256(head + manifest).digest()
        if (int(properties['FILE_SIZE']) != info.file_size or
                int(properties['METADATA_SIZE']) != 24 + length or
                base64.b64decode(properties['METADATA_HASH'], validate=True) != metadata_digest):
            raise ValueError('Payload properties do not match payload metadata')
        (dest / 'payload-manifest.pb').write_bytes(manifest)
        parsed = parse_manifest(manifest)
        summary = {name: {'size': p['size'], 'sha256': p['sha256'],
                         'operation_counts': dict(Counter(OP_NAMES.get(o[1], str(o[1])) for o in p['operations']))}
                   for name, p in parsed['partitions'].items()}
        report = {'sample': sample, 'source': source, 'source_kind': 'http-ranges' if remote else 'local-zip',
                  'zip_size': f.length if remote else Path(source).stat().st_size,
                  'etag': f.etag if remote else None, 'zip_sha256': None,
                  'metadata_files': entries, 'manifest_sha256': hashlib.sha256(manifest).hexdigest(),
                  'payload_metadata_hash_verified': True,
                  'ota_identity': dict(line.split('=', 1) for line in (dest / 'metadata').read_text().splitlines()
                                       if line.startswith(('post-', 'pre-device=', 'ota-type='))),
                  'payload_version': version, 'block_size': parsed['block_size'],
                  'payload_data_zip_offset': base, 'groups': parsed['groups'],
                  'partitions': summary, 'extracted': {},
                  'verification_scope': 'ZIP metadata CRC; operation hashes where present; full extracted partition SHA-256. No OTA signature authentication or whole ZIP digest yet.',
                  'tool_sha256': sha256_file(__file__)}
        report_path = dest / 'inventory.json'
        if report_path.exists():
            old = json.loads(report_path.read_text())
            if old.get('manifest_sha256') == report['manifest_sha256']:
                report['extracted'] = old.get('extracted', {})
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        print(f'{sample}: {len(summary)} partitions, metadata verified', flush=True)
        for name in wanted:
            if name not in parsed['partitions']:
                print(f'{sample}: {name} absent from manifest', flush=True)
                continue
            print(f'{sample}: extracting {name}', flush=True)
            report['extracted'][name] = extract_partition(f, base, position + info.file_size,
                parsed['block_size'], parsed['partitions'][name], dest / f'{name}.img')
            report['http_bytes_fetched_this_run'] = getattr(f, 'bytes_fetched', 0)
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            print(f'{sample}: {name} SHA-256 verified', flush=True)
        return report
    finally:
        f.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', nargs='+', choices=list(sources()), default=list(sources()))
    parser.add_argument('--partitions', nargs='*', default=[])
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    failures = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 5))) as pool:
        futures = {pool.submit(acquire, s, sources()[s], args.partitions): s for s in args.samples}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                failures.append(futures[future])
                print(f'FAILED {futures[future]}: {type(e).__name__}: {e}', flush=True)
    inventory = {p.parent.name: json.loads(p.read_text()) for p in sorted(SAMPLES.glob('*/inventory.json'))}
    (ROOT / 'firmware-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
