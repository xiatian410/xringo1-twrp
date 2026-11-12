#!/usr/bin/env python3
"""Encode production recorder output and decode WebM with libwebm/libvpx.

Actual worker, color converter, VP8 encoder and file muxer execute. Input is a
synthetic BGRA color-bar frame with padded stride and supplied monotonic times.
Host decoder is validation-only; no Android decoder dependency is introduced.
Sequential cases wait for encode completion. Queue cases gate the first real
encode to saturate two pending slots, drop seven frames, check copied pixels,
drain on stop or resume with original timestamps. Synthetic gating is not a
device throughput measurement; display shadow/DRM and screen lifecycle are not covered.
Decoded color checks sample the centers of the three bars, not every pixel or
odd-dimension chroma edges. Container timestamps and duration are parsed from
actual files; playback/seek in an independent player is not exercised.
"""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = Path('/root/AAA/twrp')
SRC = ANDROID / 'bootable/recovery/gui2/backend'
WEBM = ANDROID / 'external/libwebm'
VPX = ANDROID / 'external/libvpx'
LIBVPX = Path('/usr/lib/x86_64-linux-gnu/libvpx.so.9')


def main():
    out = ROOT / 'logs/video-frames'
    out.mkdir(exist_ok=True)
    files = [SRC / n for n in ['webm_vp8.cpp', 'rgb_to_i420.cpp']]
    files += [WEBM / n for n in ['mkvmuxer/mkvmuxer.cc', 'mkvmuxer/mkvmuxerutil.cc',
                                'mkvmuxer/mkvwriter.cc', 'mkvparser/mkvparser.cc', 'mkvparser/mkvreader.cc']]
    harness = ROOT / 'tests/video_frames_test.cpp'
    cases = []
    with tempfile.TemporaryDirectory(prefix='dijun-video-frames-') as temp:
        exe = Path(temp) / 'test'
        subprocess.run(['g++', '-std=c++17', '-pthread', '-g', '-O1',
                        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-no-pie',
                        '-I' + str(SRC), '-I' + str(VPX), '-I' + str(WEBM),
                        str(harness), *map(str, files), str(LIBVPX),
                        '-Wl,--wrap=vpx_codec_encode', '-o', str(exe)], check=True)
        combinations = [(96, 64, fps) for fps in [15, 24, 30, 45, 60]] + [(97, 65, 30)]
        for mode, width, height, fps in [(mode, *shape) for mode in
                                       ['sequential', 'queue-drain', 'queue-resume'] for shape in combinations]:
            suffix = '' if mode == 'sequential' else '-' + mode
            video = out / f'{width}x{height}-{fps}{suffix}.webm'
            run = subprocess.run([str(exe), str(video), str(width), str(height), str(fps), mode],
                                 capture_output=True, text=True, timeout=15)
            case = dict(mode=mode, width=width, height=height, fps=fps, status='PASS' if run.returncode == 0 else 'FAIL',
                        stdout=run.stdout, stderr=run.stderr, returncode=run.returncode,
                        artifact=str(video.relative_to(ROOT)))
            if video.exists():
                case['sha256'] = hashlib.sha256(video.read_bytes()).hexdigest()
            cases.append(case)
            print(case['status'], width, height, fps, run.stdout + run.stderr, flush=True)
    inputs = files + [harness, Path(__file__).resolve(), LIBVPX.resolve()]
    inputs += sorted(p for p in SRC.glob('*.h') if p.name in ['webm_vp8.h', 'rgb_to_i420.h', 'screen_backend.h'])
    inputs += sorted(WEBM.glob('mkvmuxer/*.h')) + sorted(WEBM.glob('mkvparser/*.h')) + sorted(VPX.glob('vpx/*.h'))
    report = dict(status='PASS' if all(c['status'] == 'PASS' for c in cases) else 'FAIL',
                  scope=__doc__.strip(), cases=cases,
                  sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    (ROOT / 'logs/video-frames.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
