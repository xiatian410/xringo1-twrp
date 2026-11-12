#!/usr/bin/env python3
"""Execute the delivered static Android ARM64 diagnostic under QEMU user mode.

Runs actual target instructions, bionic startup, argument parsing, monotonic
clock, stdio, open/close and failing evdev ioctl on a temporary regular file.
No device is attached/accessed; no FF upload/play succeeds or is simulated.
QEMU Linux-user syscall translation is not an Android kernel/SELinux/evdev test.
"""
import hashlib
import json
import subprocess
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QEMU = ROOT / 'tools/qemu-user/qemu-aarch64'
BINARY = ROOT / 'tools/haptics-diagnostic/haptics-diagnostic-arm64'


def main():
    provenance = json.loads(BINARY.with_suffix('.json').read_text())
    assert hashlib.sha256(BINARY.read_bytes()).hexdigest() == provenance['sha256']
    qemu_source = json.loads((QEMU.parent / 'source.json').read_text())
    assert hashlib.sha256(QEMU.read_bytes()).hexdigest() == qemu_source['binary_sha256']
    # A unique numeric event name ensures QEMU's fallback cannot touch a real
    # host device, even if the host has a /dev/input directory.
    path = '/dev/input/event' + str(uuid.uuid4().int)
    assert not Path(path).exists()
    cases = []
    with tempfile.TemporaryDirectory(prefix='dijun-arm64-input-root-') as temp:
        prefix = Path(temp)
        fixture = prefix / path.lstrip('/')
        fixture.parent.mkdir(parents=True)
        for label, args, expected in [
            ('usage', [], 2),
            ('duration-zero', ['--play', path, '0'], 2),
            ('duration-over-limit', ['--play', path, '10001'], 2),
            ('duration-nonnumeric', ['--play', path, 'bad'], 2),
            ('reject-non-event', ['--inspect', '/tmp/not-an-input'], 2),
            ('missing-inspect', ['--inspect', path], 1),
            ('regular-file-inspect', ['--inspect', path], 1),
            ('regular-file-play', ['--play', path, '80'], 1),
            ('stock-duration-zero', ['--stock-long', path, '0'], 2),
            ('stock-duration-limit', ['--stock-long', path, '1001'], 2),
            ('stock-duration-bad', ['--stock-long', path, 'bad'], 2),
            ('regular-file-stock', ['--stock-long', path, '80'], 1),
            ('sine-gain-duration-zero',['--sine-gain100',path,'0'],2),
            ('sine-gain-duration-limit',['--sine-gain100',path,'1001'],2),
            ('regular-file-sine-gain',['--sine-gain100',path,'80'],1),
            ('custom-existing-duration-zero',['--custom-existing-gain',path,'0'],2),
            ('custom-existing-duration-limit',['--custom-existing-gain',path,'1001'],2),
            ('regular-file-custom-existing',['--custom-existing-gain',path,'80'],1),
        ]:
            regular = label.startswith('regular-file')
            if regular:
                fixture.write_bytes(b'fixture: ordinary file, no input device\n')
            assert not Path(path).exists()
            run = subprocess.run([str(QEMU), '-L', str(prefix), str(BINARY), *args],
                                 capture_output=True, text=True, timeout=10)
            assert run.returncode == expected, (label, run.stdout, run.stderr)
            assert 'BEGIN upload' not in run.stdout and 'BEGIN play' not in run.stdout
            assert 'BEGIN gain' not in run.stdout
            if label == 'missing-inspect':
                assert 'END open result=-1 errno=2 ' in run.stdout
                assert 'BEGIN name' not in run.stdout
            elif regular:
                assert 'END name result=-1 errno=25 ' in run.stdout
                assert 'END close result=0 errno=0 ' in run.stdout
                assert fixture.read_bytes() == b'fixture: ordinary file, no input device\n'
            else:
                assert 'BEGIN open' not in run.stdout
            cases.append(dict(case=label, status='PASS', result=run.returncode,
                              stdout=run.stdout, stderr=run.stderr))
    files = [BINARY, BINARY.with_suffix('.json'), QEMU, QEMU.parent / 'source.json',
             Path(__file__).resolve(), ROOT / 'tools/haptics-diagnostic/haptics-diagnostic.c']
    report = dict(status='PASS', scope=__doc__.strip(), cases=cases,
                  sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (ROOT / 'logs/haptics-diagnostic-arm64-test.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'actual static ARM64 target cases under QEMU; no hardware/FF playback')


if __name__ == '__main__':
    main()
