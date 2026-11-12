#!/usr/bin/env python3
"""Exercise the actual extractor against corrupt and non-contiguous fixtures."""
import bz2
import hashlib
import io
import lzma
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from acquire_firmware import extract_partition, fields, payload_position


class FirmwareExtractionTest(unittest.TestCase):
    def test_compressions_extent_order_and_hash(self):
        # The first operation writes destination extents out of order.
        a, b, c, d = (bytes([i]) * 512 for i in (1, 2, 3, 4))
        final = b + c + a + d + bytes(512)
        operations, blobs = [], b''
        for kind, raw, extents in ((0, a+b, [(2, 1), (0, 1)]),
                                   (1, c, [(1, 1)]), (8, d, [(3, 1)])):
            packed = bz2.compress(raw) if kind == 1 else lzma.compress(raw) if kind == 8 else raw
            operations.append({1: kind, 2: len(blobs), 3: len(packed),
                               8: hashlib.sha256(packed).digest(), 'extents': extents})
            blobs += packed
        operations.append({1: 6, 'extents': [(4, 1)]})
        part = {'name': 'test', 'size': len(final), 'sha256': hashlib.sha256(final).hexdigest(), 'operations': operations}
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'test.img'
            result = extract_partition(io.BytesIO(b'header' + blobs), 6, 6+len(blobs), 512, part, out)
            self.assertTrue(result['verified'])
            self.assertEqual(out.read_bytes(), final)
            # Corruption must not publish an output image.
            out.unlink()
            with self.assertRaisesRegex(ValueError, 'Operation SHA-256'):
                extract_partition(io.BytesIO(b'header' + b'x' + blobs[1:]), 6, 6+len(blobs), 512, part, out)
            self.assertFalse(out.exists())
            part['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'Partition SHA-256'):
                extract_partition(io.BytesIO(b'header' + blobs), 6, 6+len(blobs), 512, part, out)
            self.assertFalse(out.exists())

    def test_reject_bad_ranges_and_patch_operations(self):
        base = {'name': 'test', 'size': 1024, 'sha256': '0' * 64}
        cases = [({1: 4, 'extents': [(0, 2)]}, 'Unsupported operation'),
                 ({1: 6, 'extents': [(0, 1)]}, 'Incomplete'),
                 ({1: 6, 'extents': [(0, 1), (0, 1)]}, 'Overlapping'),
                 ({1: 6, 'extents': [(0, 3)]}, 'Invalid destination'),
                 ({1: 0, 2: 2, 3: 1024, 'extents': [(0, 2)]}, 'outside payload')]
        with tempfile.TemporaryDirectory() as t:
            for op, message in cases:
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    extract_partition(io.BytesIO(), 0, 1, 512, dict(base, operations=[op]), Path(t)/'test.img')

    def test_zip64_local_offset(self):
        f = io.BytesIO()
        with zipfile.ZipFile(f, 'w', compression=zipfile.ZIP_STORED) as z:
            with z.open('payload.bin', 'w', force_zip64=True) as p:
                p.write(b'CrAUfixture')
        f.seek(0)
        with zipfile.ZipFile(f) as z:
            pos = payload_position(f, z.getinfo('payload.bin'))
            self.assertEqual(f.getvalue()[pos:pos+11], b'CrAUfixture')

    def test_malformed_protobuf(self):
        for value in (b'\x80', b'\x0a\x03a', b'\x00\x01', b'\x09xx', b'\x08'+b'\xff'*10):
            with self.subTest(value=value), self.assertRaises(ValueError):
                list(fields(value))


if __name__ == '__main__':
    unittest.main()
