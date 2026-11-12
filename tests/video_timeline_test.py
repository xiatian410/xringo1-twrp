#!/usr/bin/env python3
"""Production recorder multi-cluster/keyframe timeline with native FFmpeg seeks.

Generate12.5-second supplied timelines at160x96/15,30,60FPS with ten grayscale
tiles encoding each frame number. Real worker/converter/codec/muxer execute,
with sequential submission synchronized at actual encode return. No real-time
performance, target ARM64 codec, display sampling or phone is exercised. Native
FFmpeg checks all frame IDs/PTS and seeks across cluster/keyframe boundaries.
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from video_frames_test import SRC, WEBM, VPX, LIBVPX
from video_ffmpeg_test import ROOT, BIN, run, sha


def elements(blob, start, end):
    """Read bounded EBML elements, respecting declared lengths, never byte-search."""
    while start < end:
        position = start
        first = blob[start]
        assert first
        n = 1
        while not first & (0x80 >> (n - 1)):
            n += 1
        assert n <= 4 and start + n < end
        kind = int.from_bytes(blob[start:start + n], 'big')
        start += n
        first = blob[start]
        assert first
        n = 1
        while not first & (0x80 >> (n - 1)):
            n += 1
        assert n <= 8 and start + n <= end
        size = int.from_bytes(blob[start:start + n], 'big') & ((1 << (7 * n)) - 1)
        assert size != (1 << (7 * n)) - 1, 'unexpected unknown-sized file element'
        start += n
        assert start + size <= end
        yield kind, start, start + size, position
        start += size
    assert start == end


def frame_id(raw, offset=0):
    result = 0
    for bit in range(10):
        value = raw[offset + 32 * 160 + 8 + bit * 16]
        assert abs(value - 43) <= 12 or abs(value - 208) <= 12, value
        result |= (value > 128) << bit
    return result


def main():
    destination = ROOT / 'logs/video-timeline'
    destination.mkdir(exist_ok=True)
    files = [SRC / n for n in ['webm_vp8.cpp', 'rgb_to_i420.cpp']]
    files += [WEBM / n for n in ['mkvmuxer/mkvmuxer.cc', 'mkvmuxer/mkvmuxerutil.cc', 'mkvmuxer/mkvwriter.cc']]
    harness = ROOT / 'tests/video_timeline_capture.cpp'
    cases = []
    tools = json.loads((ROOT / 'tools/ffmpeg-host/source.json').read_text())
    for name, digest in tools['linked_files'].items(): assert sha(Path(name)) == digest
    frame_size = 160 * 96 * 3 // 2
    with tempfile.TemporaryDirectory(prefix='dijun-timeline-') as temp:
        exe = Path(temp) / 'capture'
        command = ['g++', '-std=c++17', '-pthread', '-O1', '-g', '-no-pie',
                   '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                   '-I' + str(SRC), '-I' + str(VPX), '-I' + str(WEBM),
                   str(harness), *map(str, files), str(LIBVPX),
                   '-Wl,--wrap=vpx_codec_encode', '-o', str(exe)]
        subprocess.run(command, check=True)
        for fps in [15, 30, 60]:
            path = destination / f'160x96-{fps}.webm'
            generated = subprocess.run([str(exe), str(path), str(fps)], capture_output=True,
                                       text=True, timeout=25)
            assert generated.returncode == 0 and not generated.stderr, generated.stderr
            blob = path.read_bytes()
            segment, = [(a, b) for k, a, b, pos in elements(blob, 0, len(blob)) if k == 0x18538067]
            children = list(elements(blob, *segment))
            clusters = [dict(position=pos, length=b - a) for k, a, b, pos in children if k == 0x1f43b675]
            assert len(clusters) >= 3 and not any(k == 0x1c53bb6b for k, *_ in children)
            probe = json.loads(run([str(BIN / 'ffprobe'), '-v', 'error', '-show_streams',
                                   '-show_format', '-show_frames', '-of', 'json', str(path)]).stdout)
            stream, = probe['streams']
            assert stream['codec_name'] == 'vp8' and (stream['width'], stream['height']) == (160, 96)
            assert abs(float(probe['format']['duration']) - 12.5) < 0.001
            count = (12500 * fps + 999) // 1000
            times = [i * 1000 // fps for i in range(count)]
            assert [round(float(f['pts_time']) * 1000) for f in probe['frames']] == times
            keys = [i for i, f in enumerate(probe['frames']) if f['key_frame']]
            assert len(keys) >= 3 and keys[0] == 0 and max(keys) >= 10 * fps
            decode = run([str(BIN / 'ffmpeg'), '-hide_banner', '-loglevel', 'info', '-nostdin',
                          '-c:v', 'vp8', '-i', str(path), '-map', '0:v:0', '-fps_mode', 'passthrough',
                          '-pix_fmt', 'yuv420p', '-f', 'rawvideo', 'pipe:1'])
            assert '(vp8 (native) -> rawvideo (native))' in decode.stderr.decode()
            assert len(decode.stdout) == count * frame_size
            assert [frame_id(decode.stdout, i * frame_size) for i in range(count)] == list(range(count))
            seeks = []
            for target in [0, 4.95, 5, 5.05, 9.95, 10, 10.05, 12.4, 12.49, 12.6]:
                command = [str(BIN / 'ffmpeg'), '-hide_banner', '-loglevel', 'info', '-nostdin',
                           '-c:v', 'vp8', '-ss', str(target), '-copyts', '-i', str(path),
                           '-map', '0:v:0', '-frames:v', '1', '-vf', 'showinfo', '-fps_mode', 'passthrough',
                           '-pix_fmt', 'yuv420p', '-f', 'rawvideo', 'pipe:1']
                result = run(command)
                pts = re.findall(r'\bn:\s*\d+\s+pts:\s*[-\d]+\s+pts_time:([-\d.]+)', result.stderr.decode())
                index = next((i for i, t in enumerate(times) if t + .001 >= target * 1000), None)
                if index is None:
                    assert not result.stdout and not pts
                else:
                    assert len(pts) == 1 and abs(float(pts[0]) * 1000 - times[index]) <= 1
                    assert frame_id(result.stdout) == index
                    assert result.stdout == decode.stdout[index * frame_size:(index + 1) * frame_size]
                seeks.append(dict(target_seconds=target, frame_id=index,
                                  pts_ms=None if index is None else times[index],
                                  decoded_sha256=__import__('hashlib').sha256(result.stdout).hexdigest(),
                                  command=command, log=result.stderr.decode()))
            cases.append(dict(status='PASS', fps=fps, frames=count, artifact=str(path.relative_to(ROOT)),
                              sha256=sha(path), clusters=clusters, cues=False, keyframe_ids=keys,
                              duration_seconds=12.5, frame_ids_checked=count, pts_ms=times,
                              producer_output=generated.stdout, probe=probe, seeks=seeks))
            print('PASS', fps, 'frames', count, 'clusters', len(clusters), 'keyframes', len(keys), 'seeks', len(seeks), flush=True)
    inputs = files + [harness, Path(__file__).resolve(), ROOT / 'tests/video_frames_test.py',
                      ROOT / 'tests/video_ffmpeg_test.py', LIBVPX.resolve()]
    inputs += [SRC / n for n in ['webm_vp8.h', 'rgb_to_i420.h', 'screen_backend.h']]
    inputs += sorted(WEBM.glob('mkvmuxer/*.h')) + sorted(VPX.glob('vpx/*.h'))
    report = dict(status='PASS', scope=__doc__.strip(), cases=cases, tools=tools,
                  sources={str(p): sha(p) for p in inputs})
    (ROOT / 'logs/video-timeline.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__': main()
