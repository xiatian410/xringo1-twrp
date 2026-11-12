#!/usr/bin/env python3
"""Run the shipped ordinary-report policy against private filesystem fixtures.

No device, kernel callback, SPI acknowledgement or touch event is emulated.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'dtsrc/O1_asic_dual/profiles/runtime/dijun-touch-reports.sh'


def main():
    cases = []
    for label in ['raw-one', 'cached-zero-still-requested', 'late-panel',
                  'missing-input', 'module-coming', 'write-fails', 'readback-mismatch']:
        with tempfile.TemporaryDirectory(prefix='dijun-touch-policy-') as temp:
            root = Path(temp)
            node = root/'sys/class/touch/touch_dev/enable_touch_raw'
            node.parent.mkdir(parents=True)
            node.write_text('0\n' if label == 'cached-zero-still-requested' else '1\n')
            module = root/'sys/module/synaptics_tcm2/initstate'
            module.parent.mkdir(parents=True)
            module.write_text('coming\n' if label == 'module-coming' else 'live\n')
            devices = root/'proc/bus/input/devices'
            devices.parent.mkdir(parents=True)
            devices.write_text('' if label in ['late-panel', 'missing-input'] else 'N: Name="Xiaomi_Touch_Input_0"\n')
            mock = root/'mockbin'; mock.mkdir()
            sleep = mock/'sleep'
            sleep.write_text('''#!/usr/bin/env python3
import os
from pathlib import Path
r=Path(os.environ['POLICY_FIXTURE'])
p=r/'sleeps'; n=int(p.read_text())+1 if p.exists() else 1; p.write_text(str(n))
if os.environ['POLICY_CASE']=='late-panel' and n==2:
    (r/'proc/bus/input/devices').write_text('N: Name="Xiaomi_Touch_Input_0"\\n')
'''); sleep.chmod(0o755)
            if label == 'write-fails':
                # /dev/full rejects writes; no physical device is accessed.
                node.unlink(); node.symlink_to('/dev/full')
            if label == 'readback-mismatch':
                cat = mock/'cat'
                cat.write_text('#!/bin/sh\ncase "$1" in */enable_touch_raw) echo 1 ;; *) exec /bin/cat "$@" ;; esac\n')
                cat.chmod(0o755)
            before = node.stat().st_mtime_ns
            result = subprocess.run(['sh', str(SCRIPT), str(root)], capture_output=True,
                                    text=True, timeout=5, env={**os.environ,
                                    'PATH':str(mock)+':'+os.environ['PATH'],
                                    'POLICY_FIXTURE':str(root), 'POLICY_CASE':label})
            success = label in ['raw-one', 'cached-zero-still-requested', 'late-panel']
            assert result.returncode == (0 if success else 1), (label, result)
            sleeps = int((root/'sleeps').read_text()) if (root/'sleeps').exists() else 0
            assert sleeps == (2 if label == 'late-panel' else 20 if label in ['missing-input','module-coming'] else 0)
            if success:
                assert node.read_text() == '0\n'
                assert node.stat().st_mtime_ns != before
                assert 'event delivery not tested' in result.stdout
            elif label in ['missing-input', 'module-coming']:
                assert node.read_text() == '1\n'
            cases.append(dict(case=label, status='PASS', exit=result.returncode,
                              sleeps=sleeps, stdout=result.stdout, stderr=result.stderr))
    sources = [SCRIPT, Path(__file__).resolve()]
    report = dict(status='PASS', count=len(cases), scope=__doc__, cases=cases,
                  sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (ROOT/'logs/touch-report-policy-test.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS:',len(cases),'ordinary-report policy fixture cases')


if __name__ == '__main__':
    main()
