#!/usr/bin/env python3
"""Check relevant init files taken from the actual unified image."""
import json
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from firmware_facts import boot_parts, ramdisk_entries, digest

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('image',type=Path)
parser.add_argument('--output',type=Path,default=Path('logs/unified-init-verification.json'))
args=parser.parse_args()
image=args.image; data=image.read_bytes()
entries={e[0]:e for e in ramdisk_entries(boot_parts(data)[1]['ramdisk'])}
names=['init.recovery.usb.rc','init.recovery.O1_asic.rc','system/etc/init/dijun-mitee.rc',
       'system/etc/init/keystore2.rc','system/etc/init/android.hardware.boot-service.xring.recovery.rc']
checks=[]
verifier=Path('/root/AAA/twrp/out/host/linux-x86/bin/host_init_verifier')
with tempfile.TemporaryDirectory(prefix='dijun-init-') as temp:
    for name in names:
        data=entries[name][-1]
        p=Path(temp)/Path(name).name;p.write_bytes(data)
        result=subprocess.run([str(verifier),str(p)],text=True,capture_output=True)
        checks.append(dict(path=name,sha256=digest(data),exit=result.returncode,diagnostic=result.stdout+result.stderr))
        assert result.returncode==0,checks[-1]
rc=entries['system/etc/init/dijun-mitee.rc'][-1].decode()
assert 'on fs' not in rc and 'exec_start' not in rc and '    interface ' not in rc
for service in ['dijun-tee-supplicant','dijun-keymint','dijun-gatekeeper']:
    assert f'on property:init.svc.{service}=stopped && property:twrp.crypto.ready=1' in rc
assert 'on property:init.svc.keystore2=restarting && property:twrp.crypto.ready=1' in rc
report=dict(status='PASS',image=str(image),image_sha256=digest(image.read_bytes()),
            scope='Production host_init_verifier syntax plus static activation/lost-service trigger assertions; not a running Android init.',checks=checks,
            test_sources={str(p):digest(p.read_bytes()) for p in
                          [Path(__file__).resolve(), Path(__file__).with_name('firmware_facts.py'), verifier]})
args.output.write_text(json.dumps(report,indent=2)+'\n')
print('PASS: five init files from actual image; no early/lazy MiTEE start; four service-loss guards')
