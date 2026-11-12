#!/usr/bin/env python3
"""Run state collector against private files, failure commands and a blocked FIFO.

No adb, physical input, sysfs, persist or kernel log access. Verifies bounded
reads, partial failure reporting, profile gating and preservation of inputs.
PowerShell and Android shell compatibility are not executed here.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from haptics_driver_emulation import Module, ROOT

SOURCE = ROOT / 'scripts/collect-haptics-state.sh'
POWERSHELL = ROOT / 'scripts/collect-haptics-state.ps1'
MOCK = '''#!/usr/bin/env python3
import os, pathlib, sys
name=pathlib.Path(sys.argv[0]).name
root=pathlib.Path(os.environ['HAPTICS_STATE_FIXTURE'])
with (root/'calls').open('a') as f:f.write(name+' '+repr(sys.argv[1:])+'\\n')
if name=='getprop':print('os3-final' if os.environ['CASE']=='unknown-profile' else 'os4-stable')
elif name=='head':
 if os.environ['CASE']=='q-read-error' and sys.argv[-1].endswith('/q_stored'):sys.exit(1)
 os.execv('/usr/bin/head',['head']+sys.argv[1:])
elif name in ['dmesg','logcat','ps']:print('synthetic-'+name)
else:raise AssertionError(name)
'''
ATTRIBUTES = {
    'default/vibe_state': 'vibe_state_show',
    'default/dsp_state': 'dsp_state_show',
    'default/fw_rev': 'fw_rev_show',
    'default/overprotection_gain': 'overprotection_gain_show',
    'calibration/f0_stored': 'f0_stored_show',
    'calibration/redc_stored': 'redc_stored_show',
    'calibration/q_stored': 'q_stored_show',
}


def attribute_evidence():
    evidence = []
    for sample in ['os4-current', 'os4-stable']:
        path = ROOT / f'firmware/samples/{sample}/analysis/vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        m = Module(path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == '969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6'
        members = {}
        for symbol in ['cs40l26_dev_attr_group', 'cs40l26_dev_attr_cal_group']:
            address = m.symbols[symbol]
            group = m.string(m.u64(address))
            array = m.u64(address + 32)
            for index in range(64):
                attr = m.u64(array + index * 8)
                if not attr:
                    break
                key = group + '/' + m.string(m.u64(attr))
                members[key] = (m.u32(attr + 8), m.u64(attr + 16))
            else:
                raise AssertionError('unterminated attribute group')
        for relative, show in ATTRIBUTES.items():
            mode, callback = members[relative]
            assert mode & 0o444 and callback == m.symbols[show], (sample, relative)
        evidence.append(dict(sample=sample, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             attributes={k: dict(mode=oct(members[k][0]), show=v)
                                         for k, v in ATTRIBUTES.items()}))
    return evidence


def main():
    cases = []
    for label in ['success', 'missing-node', 'q-read-error', 'unmounted',
                  'unknown-profile', 'no-input', 'blocked-read', 'output-exists',
                  'output-symlink', 'invalid-output', 'missing-timeout']:
        with tempfile.TemporaryDirectory(prefix='haptics-state-') as temp:
            root = Path(temp)
            mock = root / 'mock'
            mock.mkdir()
            for command in ['getprop', 'head', 'dmesg', 'logcat', 'ps']:
                p = mock / command
                p.write_text(MOCK)
                p.chmod(0o755)
            for directory in ['tmp', 'proc/bus/input', 'sys/class/input', 'mnt/vendor/persist/haptics']:
                (root / directory).mkdir(parents=True, exist_ok=True)
            for file in ['interrupts', 'uptime', 'modules', 'bus/input/devices']:
                (root / 'proc' / file).write_text('synthetic snapshot\n')
            mount = str(root / 'mnt/vendor/persist')
            (root / 'proc/mounts').write_text('' if label == 'unmounted' else f'/fixture {mount} f2fs rw 0 0\n')
            (root / 'tmp/recovery.log').write_text('fixture recovery log\n')
            for file in ['vib_cal_z', 'vib_cal_f0', 'vib_cal_q']:
                (root / 'mnt/vendor/persist/haptics' / file).write_text('1234\n')
            # Non-allowlisted content must never be copied or opened.
            (root / 'mnt/vendor/persist/secret-key').write_text('DO_NOT_COLLECT')
            for number, name in [(2, 'pwrkey'), (17, 'cs40l26_input')]:
                p = root / f'sys/class/input/input{number}'
                p.mkdir()
                (p / 'name').write_text(name + '\n')
                if number == 17:
                    for relative in ATTRIBUTES:
                        node = p / relative
                        node.parent.mkdir(exist_ok=True)
                        node.write_text('fixture-state\n')
                    (p / 'calibration/trigger_calibration').write_text('DO_NOT_READ')
            input_path = root / 'sys/class/input/input17'
            target = input_path / 'calibration/f0_stored'
            if label == 'missing-node':
                target.unlink()
            elif label == 'blocked-read':
                target.unlink()
                os.mkfifo(target)
            elif label == 'no-input':
                (input_path / 'name').write_text('other-input\n')
            output = root / 'tmp/dijun-haptics-state-123'
            if label == 'output-exists':
                output.mkdir()
                (output / 'marker').write_text('preserve')
            elif label == 'output-symlink':
                output.symlink_to(root / 'mnt/vendor/persist', target_is_directory=True)
            elif label == 'invalid-output':
                output = root / 'mnt/vendor/persist'
            original = {p: p.read_bytes() for base in ['sys', 'proc', 'mnt']
                        for p in (root / base).rglob('*') if p.is_file()}
            text = SOURCE.read_text()
            for prefix in ['/tmp/', '/sys/', '/proc/', '/mnt/']:
                text = text.replace(prefix, str(root) + prefix)
            script = root / 'collector.sh'
            script.write_text(text)
            env = dict(os.environ, PATH=str(mock) + ':/usr/bin:/bin',
                       HAPTICS_STATE_FIXTURE=str(root), CASE=label)
            if label == 'missing-timeout':
                env['PATH'] = str(mock)
            result = subprocess.run(['/bin/sh', str(script), str(output)], env=env,
                                    text=True, capture_output=True, timeout=15)
            for path, contents in original.items():
                assert path.read_bytes() == contents, (label, path)
            rejected = label in ['output-exists', 'output-symlink', 'invalid-output', 'missing-timeout']
            if rejected:
                assert result.returncode != 0 and not (output / 'commands.tsv').exists(), label
                if label == 'output-exists':
                    assert (output / 'marker').read_text() == 'preserve'
            else:
                expected = 0 if label == 'success' else 1
                assert result.returncode == expected, (label, result.stdout, result.stderr)
                assert (output / 'collection-exit.txt').read_text().strip() == str(expected)
                state = (output / 'haptics-state.txt').read_text()
                calls = (root / 'calls').read_text()
                assert 'secret-key' not in calls and 'trigger_calibration' not in calls
                assert 'DO_NOT_COLLECT' not in ''.join(p.read_text() for p in output.iterdir())
                if label in ['unknown-profile', 'no-input']:
                    assert '/calibration/' not in calls and '/default/' not in calls
                if label == 'unknown-profile':
                    assert 'UNREVIEWED_PROFILE=os3-final' in state
                if label == 'blocked-read':
                    assert 'READ_EXIT=137' in state and 'READ_EXIT=0' in state
                if label == 'missing-node':
                    assert 'READ_EXIT=MISSING_OR_UNREADABLE' in state
                if label == 'q-read-error':
                    assert 'READ_EXIT=1' in state
                if label == 'unmounted':
                    assert 'PERSIST_NOT_MOUNTED' in (output / 'persist-calibration.txt').read_text()
                    assert 'vib_cal_' not in calls
                if label == 'success':
                    assert state.count('READ_EXIT=0') == 7 and 'MATCHING_INPUTS=1' in state
                assert calls.index('dmesg ') < calls.index('head ')
            cases.append(dict(case=label, status='PASS', returncode=result.returncode))
    report = dict(status='PASS', count=len(cases), scope=__doc__, cases=cases,
                  original_elf_attribute_evidence=attribute_evidence(),
                  sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [SOURCE, POWERSHELL, Path(__file__).resolve(),
                                     ROOT/'logs/os4-stable-haptics-readonly-shows.disasm']})
    (ROOT / 'logs/haptics-state-collector-test.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'private collector scenarios; two original OS4 attribute groups checked')


if __name__ == '__main__':
    main()
