#!/usr/bin/env python3
"""Execute production recorder error propagation and same-object recovery.

Private regular output files, real libwebm and host libvpx are used. Explicit
stdio/codec wrappers inject open, write, flush, close and codec errors. Close
actually releases its FILE before returning an injected EIO. A later recording
on the same object executes without injection. No target kernel, storage,
display, power loss or real disk-full device is exercised.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from video_frames_test import ROOT, SRC, WEBM, VPX, LIBVPX


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SRC / 'webm_vp8.cpp')
    parser.add_argument('--output', type=Path, default=ROOT / 'logs/video-failure.json')
    args = parser.parse_args()
    files = [args.source, SRC / 'rgb_to_i420.cpp']
    files += [WEBM / n for n in ['mkvmuxer/mkvmuxer.cc', 'mkvmuxer/mkvmuxerutil.cc', 'mkvmuxer/mkvwriter.cc']]
    harness = ROOT / 'tests/video_failure_test.cpp'
    cases = []
    with tempfile.TemporaryDirectory(prefix='dijun-video-failure-') as temp:
        exe = Path(temp) / 'test'
        subprocess.run(['g++', '-std=c++17', '-pthread', '-g', '-O1',
                        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-no-pie',
                        '-I' + str(SRC), '-I' + str(VPX), '-I' + str(WEBM),
                        str(harness), *map(str, files), str(LIBVPX),
                        *['-Wl,--wrap=' + f for f in ['fopen', 'fwrite', 'fflush', 'fclose', 'vpx_codec_encode']],
                        '-o', str(exe)], check=True)
        for label in ['open', 'write', 'flush', 'close', 'codec', 'codec-close']:
            run = subprocess.run([str(exe), str(Path(temp) / (label + '.webm')), label],
                                 capture_output=True, text=True, timeout=15)
            cases.append(dict(case=label, status='PASS' if run.returncode == 0 else 'FAIL',
                              returncode=run.returncode, stdout=run.stdout, stderr=run.stderr))
            print(label, run.returncode, run.stdout + run.stderr, flush=True)
    inputs = files + [harness, Path(__file__).resolve(), ROOT / 'tests/video_frames_test.py', LIBVPX.resolve()]
    inputs += [SRC / n for n in ['webm_vp8.h', 'rgb_to_i420.h', 'screen_backend.h']]
    inputs += sorted(WEBM.glob('mkvmuxer/*.h')) + sorted(VPX.glob('vpx/*.h'))
    report = dict(status='PASS' if all(c['status'] == 'PASS' for c in cases) else 'FAIL',
                  scope=__doc__.strip(), cases=cases,
                  sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
