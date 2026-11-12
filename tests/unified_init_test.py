#!/usr/bin/env python3
"""Check selected rc files from the candidate using production host_init_verifier.

This validates syntax and explicit service gating; it does not run Android init
or emulate the full ramdisk merge, property scheduler or hardware boot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from verify_devicefix import entries

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('image', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
data, ramdisk = entries(args.image)
names = ['system/etc/init/hw/init.rc', 'init.recovery.usb.rc', 'init.recovery.O1_asic.rc',
         'system/etc/init/dijun-mitee.rc', 'system/etc/init/keystore2.rc',
         'system/etc/init/android.hardware.boot-service.xring.recovery.rc']
verifier = Path('/root/AAA/twrp/out/host/linux-x86/bin/host_init_verifier')
checks = []
with tempfile.TemporaryDirectory(prefix='dijun-init-check-') as temp:
    for name in names:
        content = ramdisk[name][11]
        path = Path(temp)/Path(name).name
        path.write_bytes(content)
        run = subprocess.run([str(verifier), str(path)], capture_output=True, text=True, timeout=15)
        checks.append(dict(path=name, sha256=hashlib.sha256(content).hexdigest(),
                           exit=run.returncode, diagnostic=run.stdout+run.stderr))
        assert run.returncode == 0, checks[-1]
mitee = ramdisk['system/etc/init/dijun-mitee.rc'][11].decode()
for name in ['dijun-tee-supplicant', 'dijun-keymint', 'dijun-gatekeeper']:
    block = re.search(r'^service '+name+r' .*(?:\n[ \t]+[^\n]*)*', mitee, re.M)
    assert block, name
    lines = [line.strip() for line in block[0].splitlines()[1:]]
    assert 'disabled' in lines and 'oneshot' in lines, name
    assert not any(line.startswith('interface ') for line in lines), name
for state in ['dijun-tee-supplicant=stopped', 'dijun-keymint=stopped',
              'dijun-gatekeeper=stopped', 'keystore2=restarting']:
    trigger = 'on property:init.svc.'+state+' && property:twrp.crypto.ready=1'
    assert trigger+'\n    setprop twrp.crypto.ready 0\n    setprop twrp.profile.state service-lost' in mitee
keystore = ramdisk['system/etc/init/keystore2.rc'][11].decode()
assert not re.search(r'^\s*critical(?:\s|$)', keystore, re.M)
report = dict(status='PASS', image=str(args.image), image_sha256=hashlib.sha256(data).hexdigest(),
              scope=__doc__.strip(), checks=checks,
              verifier_sha256=hashlib.sha256(verifier.read_bytes()).hexdigest(),
              test_sources={str(Path(__file__).resolve()):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(f'PASS: {len(names)} image rc files; disabled/oneshot/no-lazy MiTEE services; readiness revoked on service loss.')
