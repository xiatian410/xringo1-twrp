#!/usr/bin/env python3
"""Verify diagnostic syscall ordering/failures with no actual device access."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools/haptics-diagnostic/haptics-diagnostic.c'


def main():
    cases = []
    with tempfile.TemporaryDirectory(prefix='dijun-diagnostic-test-') as temp:
        exe = Path(temp) / 'test'
        subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-no-pie',
                        str(SOURCE), str(ROOT / 'tests/haptics_diagnostic_fixture.c'),
                        *['-Wl,--wrap=' + n for n in ['open', 'ioctl', 'write', 'nanosleep', 'close']],
                        '-o', str(exe)], check=True)
        for label in ['success', 'inspect', 'open-error', 'name-error', 'caps-error',
                      'wrong-device', 'unsupported', 'upload-error', 'invalid-id',
                      'play-short', 'play-error', 'erase-error', 'close-error', 'sleep-interrupted',
                      'stock-success', 'stock-no-custom', 'stock-no-gain', 'stock-gain-error',
                      'stock-gain-short', 'stock-upload-error', 'stock-play-error', 'stock-erase-error',
                      'sine-gain-success','sine-gain-no-gain','sine-gain-no-sine',
                      'sine-gain-write-error','sine-gain-write-short','sine-gain-upload-error',
                      'custom-success','custom-no-gain','custom-no-custom','custom-upload-error']:
            args = ['--inspect', '/dev/input/event4'] if label == 'inspect' else ['--play', '/dev/input/event4', '80']
            if label.startswith('stock-'): args[0] = '--stock-long'
            if label.startswith('sine-gain-'): args[0] = '--sine-gain100'
            if label.startswith('custom-'): args[0] = '--custom-existing-gain'
            run = subprocess.run([str(exe)] + args, capture_output=True, text=True,
                                 env={**os.environ, 'DIAGNOSTIC_CASE': label}, timeout=5)
            assert run.returncode == (0 if label in ['success', 'inspect', 'sleep-interrupted', 'stock-success','sine-gain-success','custom-success','custom-no-gain'] else 1), (label, run.stdout, run.stderr)
            if label == 'inspect':
                assert 'BEGIN upload' not in run.stdout and 'BEGIN play' not in run.stdout
            if label == 'success':
                effect = next(l.split()[1] for l in run.stdout.splitlines() if l.startswith('EFFECT_HEX '))
                # Compare all ABI bytes against the existing capture compiled
                # from actual Recovery source, normalizing allocated id to -1.
                prior = json.loads((ROOT / 'logs/haptics-driver-emulation.json').read_text())
                captured = bytearray.fromhex(next(c['effect_hex'] for c in prior['fixture_bytes'] if c['requested_ms'] == 80))
                captured[2:4] = b'\xff\xff'
                assert effect == captured.hex()
            if label == 'stock-success':
                prior = json.loads((ROOT / 'logs/haptics-service-request-emulation.json').read_text())
                original = next(c for c in prior['cases'] if c['case'] == 'service-request-80')['operations']
                expected = bytearray.fromhex(original[1]['effect'])
                actual = bytearray.fromhex(next(l.split()[1] for l in run.stdout.splitlines() if l.startswith('EFFECT_HEX ')))
                # Both point to live 2-word arrays at their own addresses.
                expected[40:48] = actual[40:48] = bytes(8)
                assert actual == expected
                custom = next(l.split()[1] for l in run.stdout.splitlines() if l.startswith('CUSTOM_HEX '))
                assert custom == original[1]['custom']
                operations = [l.split()[1] for l in run.stdout.splitlines() if l.startswith('BEGIN ')]
                assert operations == ['open','name','capabilities','gain','upload','play','erase','close']
            if label in ['stock-no-custom','stock-no-gain','stock-gain-error','stock-gain-short']:
                assert 'BEGIN upload' not in run.stdout and 'BEGIN play' not in run.stdout
            if label in ['sine-gain-success','custom-success','custom-no-gain']:
                operations=[l.split()[1] for l in run.stdout.splitlines() if l.startswith('BEGIN ')]
                assert operations==['open','name','capabilities']+(['gain'] if label.startswith('sine-') else [])+['upload','play','erase','close']
                actual=bytearray.fromhex(next(l.split()[1] for l in run.stdout.splitlines() if l.startswith('EFFECT_HEX ')))
                if label.startswith('sine-'):
                    prior=json.loads((ROOT/'logs/haptics-driver-emulation.json').read_text())
                    expected=bytearray.fromhex(next(c['effect_hex'] for c in prior['fixture_bytes'] if c['requested_ms']==80));expected[2:4]=b'\xff\xff'
                else:
                    prior=json.loads((ROOT/'logs/haptics-service-request-emulation.json').read_text())
                    original=next(c for c in prior['cases'] if c['case']=='service-request-80')['operations']
                    expected=bytearray.fromhex(original[1]['effect']);actual[40:48]=expected[40:48]=bytes(8)
                    assert next(l.split()[1] for l in run.stdout.splitlines() if l.startswith('CUSTOM_HEX '))==original[1]['custom']
                assert actual==expected
            if label in ['sine-gain-no-gain','sine-gain-no-sine','sine-gain-write-error','sine-gain-write-short','custom-no-custom']:
                assert 'BEGIN upload' not in run.stdout and 'BEGIN play' not in run.stdout
            cases.append(dict(case=label, status='PASS', result=run.returncode,
                              stdout=run.stdout, stderr=run.stderr))
        for args in [[], ['--play', '/dev/input/event4', '0'], ['--play', '/dev/input/event4', '10001'],
                     ['--play', '/dev/input/event4', 'bad'], ['--inspect', '/dev/input/event'],
                     ['--inspect', '/dev/input/event4/../x'],
                     ['--stock-long', '/dev/input/event4','0'],
                     ['--stock-long', '/dev/input/event4','1001'],
                     ['--stock-long', '/dev/input/event4','bad'],
                     *[[mode,'/dev/input/event4',value] for mode in ['--sine-gain100','--custom-existing-gain'] for value in ['0','1001','bad']]]:
            run = subprocess.run([str(exe)] + args, capture_output=True, text=True, timeout=5)
            assert run.returncode == 2 and 'BEGIN open' not in run.stdout
            cases.append(dict(case='reject-' + repr(args), status='PASS', result=2))
    paths = [SOURCE, Path(__file__).resolve(), ROOT / 'tests/haptics_diagnostic_fixture.c',
             ROOT / 'logs/haptics-driver-emulation.json', ROOT / 'logs/haptics-service-request-emulation.json']
    report = dict(status='PASS', scope=__doc__.strip(), cases=cases,
                  sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (ROOT / 'logs/haptics-diagnostic-test.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'cases; host syscall fixtures only, no ARM64 runtime/device execution')


if __name__ == '__main__':
    main()
