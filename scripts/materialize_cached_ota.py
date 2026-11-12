#!/usr/bin/env python3
"""Complete a pinned range cache and materialize a local ordinary OTA ZIP.

Missing ranges use If-Match and exact Content-Range checks. All cached chunks
must have expected sizes; final payload SHA-256 must match payload_properties.
No unverified output is published, and no image or cache is uploaded to GitHub.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import struct
import urllib.request
import zipfile

from acquire_firmware import payload_position

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', default='os4-stable', choices=['os4-stable'])
    args = parser.parse_args()
    folder = ROOT/'firmware/samples'/args.sample
    inventory = json.loads((folder/'inventory.json').read_text())
    pin = inventory['parallel_range_cache']['pin']
    assert pin['url'] == inventory['source'] and pin['size'] == inventory['zip_size']
    assert pin['url'].startswith('https://') and pin['etag'] and not pin['etag'].startswith('W/')
    cache = folder/'range-cache'
    starts = list(range(0, pin['size'], pin['chunk']))
    missing = [s for s in starts if not (cache/str(s)).is_file()]
    def fetch(start):
        end = min(start + pin['chunk'], pin['size']) - 1
        request = urllib.request.Request(pin['url'], headers={
            'Range': f'bytes={start}-{end}', 'If-Match': pin['etag'], 'Accept-Encoding': 'identity'})
        with urllib.request.urlopen(request, timeout=45) as response:
            assert response.status == 206
            assert response.headers['Content-Range'] == f'bytes {start}-{end}/{pin["size"]}'
            assert response.headers['ETag'] == pin['etag']
            data = response.read(end-start+2)
            assert len(data) == end-start+1
        partial = cache/(str(start)+'.partial')
        partial.write_bytes(data); partial.replace(cache/str(start))
        print('Fetched missing range', start, len(data), flush=True)
    print('Missing chunks:', len(missing), 'of', len(starts), flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(fetch, missing))
    output = folder/'original-ota.zip'
    partial = output.with_suffix('.zip.partial')
    sha = hashlib.sha256()
    chunks = {}
    with partial.open('wb') as dest:
        for start in starts:
            data = (cache/str(start)).read_bytes()
            assert len(data) == min(pin['chunk'], pin['size']-start), start
            chunks[str(start)] = hashlib.sha256(data).hexdigest()
            sha.update(data); dest.write(data)
    properties = dict(line.split('=',1) for line in (folder/'payload_properties.txt').read_text().splitlines())
    with partial.open('rb') as f, zipfile.ZipFile(f) as z:
        info = z.getinfo('payload.bin')
        assert info.file_size == int(properties['FILE_SIZE'])
        offset = payload_position(f, info)
        f.seek(offset); header = f.read(24)
        magic, version, size, signature = struct.unpack('>4sQQI', header)
        assert magic == b'CrAU' and version == 2 and 24+size == int(properties['METADATA_SIZE'])
        manifest = f.read(size)
        assert hashlib.sha256(manifest).hexdigest() == inventory['manifest_sha256']
        assert hashlib.sha256(header+manifest).digest() == base64.b64decode(properties['METADATA_HASH'])
        f.seek(offset); payload_hash = hashlib.sha256(); remaining = info.file_size
        while remaining:
            data = f.read(min(8*1024*1024, remaining)); assert data
            payload_hash.update(data); remaining -= len(data)
        assert payload_hash.digest() == base64.b64decode(properties['FILE_HASH'])
        assert z.read('payload_properties.txt').decode().splitlines() == (folder/'payload_properties.txt').read_text().splitlines()
    partial.replace(output)
    report = dict(status='PASS', sample=args.sample, output=str(output), size=pin['size'], sha256=sha.hexdigest(),
        pin=pin, fetched_chunks=missing, chunk_hashes=chunks, payload_offset=offset,
        payload_size=info.file_size, payload_sha256=payload_hash.hexdigest(),
        manifest_sha256=inventory['manifest_sha256'], signature_authentication=False)
    (ROOT/'logs/ota-stock-stable-materialization.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS materialized',output,sha.hexdigest(),flush=True)


if __name__=='__main__': main()
