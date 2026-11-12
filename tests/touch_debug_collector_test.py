#!/usr/bin/env python3
"""Execute the collector with private files and synthetic command boundaries.

No adb, device nodes, controller or kernel log is accessed. Validates verbosity
readback/restoration and failure reporting, not target shell compatibility.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'scripts/collect-touch-v1-debug.sh'
MOCK = '''#!/usr/bin/env python3
import os, pathlib, sys
root=pathlib.Path(os.environ['COLLECTOR_FIXTURE'])
name=pathlib.Path(sys.argv[0]).name
with (root/'calls').open('a') as f:f.write(name+' '+repr(sys.argv[1:])+'\\n')
if name=='cat':
 for value in sys.argv[1:]:
  p=pathlib.Path(value)
  if p.name=='touch_log_level':
   levels=p.read_text().split()
   if os.environ['CASE']=='invalid-original' and levels==['3','3']:print('unparseable');continue
   if os.environ['CASE']=='enable-readback-failed' and levels==['3','4']:print('unparseable');continue
   if os.environ['CASE']=='restore-readback-failed' and levels==['3','3'] and (root/'enabled').exists():print('unparseable');continue
   if levels==['3','4']:(root/'enabled').touch()
   print('current xiaomi_touch log_level = '+levels[0]+', vendor log_level = '+levels[1])
  elif p.exists():sys.stdout.write(p.read_text())
  else:sys.exit(1)
elif name=='timeout':
 assert sys.argv[1:3]==['-s','KILL']
 if sys.argv[4]=='getevent':
  print('add device 1: /dev/input/event3')
  sys.exit(1 if os.environ['CASE']=='getevent-failed' else 137)
 assert sys.argv[4:]==['dmesg','-w']
 print('[ 100.000000] synthetic-v1-debug-header')
 sys.exit(124)
elif name=='dmesg':print('[ 90.000000] synthetic snapshot')
else:raise AssertionError(name)
'''


def main():
    cases=[]
    for label in ['success','invalid-original','enable-readback-failed',
                  'restore-readback-failed','getevent-failed']:
        with tempfile.TemporaryDirectory(prefix='dijun-collector-') as temp:
            root=Path(temp); mock=root/'mock';mock.mkdir()
            for command in ['cat','timeout','dmesg']:
                p=mock/command;p.write_text(MOCK);p.chmod(0o755)
            node=root/'sys/class/touch/touch_dev/touch_log_level'
            node.parent.mkdir(parents=True);node.write_text('3 3\n')
            (node.parent/'enable_touch_raw').write_text('0\n')
            (root/'proc').mkdir()
            (root/'proc/uptime').write_text('100.00 500.00\n')
            (root/'proc/interrupts').write_text('fixture IRQ snapshot\n')
            info=root/'sys/bus/platform/devices/synaptics_tcm.0/synaptics_tcm/info'
            info.parent.mkdir(parents=True);info.write_text('Application Firmware\n')
            (root/'tmp').mkdir()
            source=SOURCE.read_text()
            for prefix in ['/tmp/','/sys/','/proc/']:
                source=source.replace(prefix,str(root)+prefix)
            script=root/'collector.sh';script.write_text(source)
            env=dict(os.environ,PATH=str(mock)+os.pathsep+os.environ['PATH'],
                     COLLECTOR_FIXTURE=str(root),CASE=label)
            result=subprocess.run(['sh',str(script)],env=env,text=True,capture_output=True,timeout=10)
            output=root/'tmp/dijun-touch-v1-debug'
            assert node.read_text()=='3 3\n', (label,result.stdout,result.stderr)
            if label in ['invalid-original','enable-readback-failed','restore-readback-failed']:
                assert result.returncode!=0,label
                if label!='restore-readback-failed':assert not (output/'events.txt').exists()
            else:
                assert result.returncode==(1 if label=='getevent-failed' else 0),(label,result.stderr)
                assert (output/'getevent-exit.txt').read_text().strip()==('1' if label=='getevent-failed' else '137')
                assert (output/'dmesg-stream-exit.txt').read_text().strip()=='124'
                if label=='success':assert 'original log verbosity restored' in result.stdout
                else:assert 'capture ended unexpectedly' in result.stderr
            if label=='restore-readback-failed':assert 'could not verify' in result.stderr
            cases.append(dict(case=label,status='PASS',returncode=result.returncode,
                              stdout=result.stdout,stderr=result.stderr))
    report=dict(status='PASS',scope=__doc__.strip(),count=len(cases),cases=cases,
                sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in [Path(__file__).resolve(),SOURCE]})
    (ROOT/'logs/touch-debug-collector-test.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS:',len(cases),'collector execution cases with private fixtures')


if __name__=='__main__':main()
