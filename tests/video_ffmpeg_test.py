#!/usr/bin/env python3
"""Read actual recorder samples with FFmpeg's independent native VP8 decoder.

Validates ffprobe metadata/timestamps, native decoder pixel centers and bounded
input seeks against linear decoded frame bytes. Existing short synthetic host
samples have one cluster and no cues; this is not a long-file seek, real-time
GUI player, target codec/display or phone throughput test. Tools are unpacked
Debian packages in the workspace, using recorded host shared libraries.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools/ffmpeg-host'
BIN = TOOLS / 'root/usr/bin'
ENV = dict(os.environ, LD_LIBRARY_PATH=str(TOOLS / 'root/usr/lib/x86_64-linux-gnu'))


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def run(command):
    result = subprocess.run(command, env=ENV, capture_output=True, timeout=15)
    assert result.returncode == 0, (command, result.stderr.decode(errors='replace'))
    return result


def tool_provenance():
    packages = {}
    for package in ['ffmpeg', 'libavdevice61']:
        deb, = TOOLS.glob(package.replace('61', '') + '*.deb')
        metadata = subprocess.check_output(['apt-cache', 'show', package], text=True)
        sections = [dict(line.split(': ', 1) for line in section.splitlines() if ': ' in line)
                    for section in metadata.strip().split('\n\n')]
        matches = [s for s in sections if s.get('SHA256') == sha(deb)]
        assert len(matches) == 1, ('package digest not in apt metadata', package)
        entry = matches[0]
        packages[package] = dict(file=str(deb.relative_to(ROOT)), sha256=sha(deb),
                                 version=entry['Version'], filename=entry['Filename'],
                                 source_url='http://deb.debian.org/debian/' + entry['Filename'],
                                 apt_metadata=metadata)
    files, versions, linking = {}, {}, {}
    for name in ['ffmpeg', 'ffprobe']:
        p = BIN / name
        files[str(p)] = sha(p)
        versions[name] = run([str(p), '-version']).stdout.decode()
        ldd = run(['ldd', str(p)]).stdout.decode()
        assert 'not found' not in ldd
        linking[name] = ldd
        for line in ldd.splitlines():
            match = re.search(r'(?:=>\s+)?(/\S+)\s+\(', line)
            if match:
                library = Path(match[1]).resolve()
                files[str(library)] = sha(library)
    decoders = run([str(BIN / 'ffmpeg'), '-hide_banner', '-decoders']).stdout.decode()
    assert re.search(r'^ V\S*\s+vp8\s+', decoders, re.M)
    return dict(packages=packages, versions=versions, linked_files=files,
                linking=linking, decoder='vp8 (native), explicitly selected by -c:v vp8')


def check_pixels(raw, width, height, count):
    cw, ch = (width + 1) // 2, (height + 1) // 2
    frame_size = width * height + 2 * cw * ch
    assert len(raw) == count * frame_size
    expected = [(82, 90, 240), (144, 54, 34), (41, 240, 110)]
    for index in range(count):
        start = index * frame_size
        for col in range(3):
            x = width * (2 * col + 1) // 6
            offsets = [width * (height // 2) + x,
                       width * height + cw * (height // 4) + x // 2,
                       width * height + cw * ch + cw * (height // 4) + x // 2]
            assert all(abs(raw[start + offset] - value) <= 8
                       for offset, value in zip(offsets, expected[col]))
    return frame_size


def main():
    original_path = ROOT / 'logs/video-frames.json'
    original = json.loads(original_path.read_text())
    assert original['status'] == 'PASS' and len(original['cases']) == 18
    # Refuse stale producer inputs; an old sample is not evidence for new code.
    for name, digest in original['sources'].items(): assert sha(Path(name)) == digest, name
    provenance = tool_provenance()
    (TOOLS / 'source.json').write_text(json.dumps(provenance, indent=2) + '\n')
    cases = []
    for case in original['cases']:
        path = ROOT / case['artifact']
        assert sha(path) == case['sha256']
        mode, fps, width, height = (case[k] for k in ['mode', 'fps', 'width', 'height'])
        expected_times = ([i * 1000 // fps for i in range(12)] if mode == 'sequential'
                          else [0, 100, 200] + ([1000] if mode == 'queue-resume' else []))
        probe_command = [str(BIN / 'ffprobe'), '-v', 'error', '-show_streams', '-show_format',
                         '-show_frames', '-of', 'json', str(path)]
        probe_run = run(probe_command)
        assert not probe_run.stderr
        probe = json.loads(probe_run.stdout)
        stream, = probe['streams']
        assert stream['codec_name'] == 'vp8' and stream['codec_type'] == 'video'
        assert (stream['width'], stream['height'], stream['pix_fmt']) == (width, height, 'yuv420p')
        assert abs(float(probe['format']['duration']) - 1.5) < 0.001
        times = [round(float(f['pts_time']) * 1000) for f in probe['frames']]
        assert times == expected_times and probe['frames'][0]['key_frame'] == 1
        decode_command = [str(BIN / 'ffmpeg'), '-hide_banner', '-loglevel', 'info', '-nostdin',
                          '-c:v', 'vp8', '-i', str(path), '-map', '0:v:0',
                          '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', 'pipe:1']
        decoded = run(decode_command)
        decode_log = decoded.stderr.decode()
        assert '(vp8 (native) -> rawvideo (native))' in decode_log
        frame_size = check_pixels(decoded.stdout, width, height, len(times))
        seeks = []
        # Seek into existing frames, the dropped-frame gap, and after the last
        # frame. Accurate input seeking decodes from the available keyframe.
        for target in [0, 0.15, 0.5, 1.2]:
            command = [str(BIN / 'ffmpeg'), '-hide_banner', '-loglevel', 'info', '-nostdin',
                       '-c:v', 'vp8', '-ss', str(target), '-copyts', '-i', str(path),
                       '-map', '0:v:0', '-frames:v', '1', '-vf', 'showinfo',
                       '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', 'pipe:1']
            sought = run(command)
            log = sought.stderr.decode()
            matches = re.findall(r'\bn:\s*\d+\s+pts:\s*[-\d]+\s+pts_time:([-\d.]+)', log)
            index = next((i for i, t in enumerate(times) if t + 0.001 >= target * 1000), None)
            if index is None:
                assert not sought.stdout and not matches, (case['artifact'], target, matches)
            else:
                assert len(matches) == 1 and abs(float(matches[0]) * 1000 - times[index]) <= 1
                assert sought.stdout == decoded.stdout[index * frame_size:(index + 1) * frame_size]
            seeks.append(dict(target_seconds=target, expected_pts_ms=None if index is None else times[index],
                              output_bytes=len(sought.stdout),
                              sha256=hashlib.sha256(sought.stdout).hexdigest(),
                              command=command, log=log))
        cases.append(dict(status='PASS', mode=mode, width=width, height=height, fps=fps,
                          artifact=case['artifact'], sha256=sha(path), pts_ms=times,
                          duration_seconds=1.5, decoded_frames=len(times),
                          decoded_sha256=hashlib.sha256(decoded.stdout).hexdigest(),
                          probe_command=probe_command, probe=probe, decode_command=decode_command,
                          decode_log=decode_log, seeks=seeks))
        print('PASS', mode, width, height, fps, 'native_frames=', len(times), 'seeks=', len(seeks), flush=True)
    result = dict(status='PASS', scope=__doc__.strip(), cases=cases,
                  producer_report=str(original_path.relative_to(ROOT)), producer_report_sha256=sha(original_path),
                  tools=provenance,
                  sources={str(Path(__file__).resolve()): sha(Path(__file__).resolve())})
    (ROOT / 'logs/video-ffmpeg.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: 18 independently decoded files and72 bounded input seeks')


if __name__ == '__main__': main()
