#!/usr/bin/env python3
"""Run production shell against module state races, never actual insmod.

Real OTA bytes, private sysfs/property fixtures. Sleep is substituted with
deterministic state transitions to exercise the bounded wait without timing
flakiness. Unknown fixture operations fail. Does not run kernel module init.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
import unittest

from profile_runtime_test import Runtime, ROOT, SAMPLES
import profile_runtime_test as runtime

TRANSITION=r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
r=Path(os.environ['FIXTURE_ROOT'])
assert sys.argv[1:]==['0.1']
parent=Path(f'/proc/{os.getppid()}/cmdline').read_bytes().split(b'\0')
scripts=[Path(a.decode()).name for a in parent if a.endswith(b'.sh')]
assert len(scripts)==1 and scripts[0] in ['dijun-runtime.sh','dijun-touch-reports.sh'],parent
kind='module' if scripts[0]=='dijun-runtime.sh' else 'touch-reports'
p=r/(kind+'-sleeps');count=int(p.read_text())+1 if p.exists() else 1;p.write_text(str(count))
transition=r/'transition.json'
if kind=='module' and transition.exists():
 t=json.loads(transition.read_text())
 if count==t['after']:
  state=r/'sys/module'/t['module']/'initstate'
  if t['to']=='absent':state.unlink();state.parent.rmdir()
  else:state.write_text(t['to']+'\n')
'''


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class States(Runtime):
    # Load only these tests; inherited runtime suite runs independently.
    def fixture(self,sample='os4-stable'):
        root=super().fixture(sample)
        if args.script:(root/'system/bin/dijun-runtime.sh').write_bytes(args.script.read_bytes())
        p=root/'mockbin/sleep';p.write_text(TRANSITION);p.chmod(0o755)
        return root

    def run_phase(self, root, phase, expected=0, **env):
        # This suite tests module states. Model immediate input registration
        # when the mock haptics module loads, so unrelated input polling cannot
        # change a module transition or its retry budget.
        return super().run_phase(root, phase, expected, HAPTICS_INPUT='immediate', **env)

    def state(self,root,name,value):
        node=root/'sys/module'/name;node.mkdir(exist_ok=True)
        p=node/'initstate'
        if value is None:
            if p.exists():p.unlink()
        else:p.write_text(value+'\n')

    def test_nonlive_hard_dependency(self):
        for state in ['coming','going','unknown',None]:
            with self.subTest(state=state):
                root=self.fixture();self.state(root,'xr_doze',state)
                self.run_phase(root,'cache');self.run_phase(root,'modules')
                loaded=[Path(c[1]).stem for c in self.calls(root) if c[0]=='insmod']
                self.assertNotIn('synaptics_tcm2',loaded)
                self.assertNotIn('xr_doze',loaded)
                self.assertEqual(self.props(root)['twrp.profile.modules'],'partial')
                self.assertEqual(self.props(root)['twrp.profile.touch_modules'],'failed')
                count=int((root/'module-sleeps').read_text()) if (root/'module-sleeps').exists() else 0
                self.assertEqual(count,20 if state=='coming' else 0)
                # The optional haptics dependency closure is independent of
                # failed touch. It must still be allowed to finish loading.
                self.assertIn('xring_audio_hw_third',loaded)
                self.assertEqual(self.props(root)['twrp.profile.haptics_input'],'registered')

    def test_initializing_touch_lifecycle(self):
        for target in ['live','going','absent','coming']:
            with self.subTest(target=target):
                root=self.fixture();self.state(root,'synaptics_tcm2','coming')
                (root/'transition.json').write_text(json.dumps(dict(module='synaptics_tcm2',after=2,to=target)))
                self.run_phase(root,'cache');self.run_phase(root,'modules')
                self.assertFalse(any(c[0]=='insmod' and Path(c[1]).stem=='synaptics_tcm2' for c in self.calls(root)))
                self.assertEqual(self.props(root)['twrp.profile.touch_modules'],'loaded' if target=='live' else 'failed')
                self.assertEqual(self.props(root)['twrp.profile.modules'],'complete' if target=='live' else 'partial')

    def test_cache_retains_initializing_module_bytes(self):
        for sample in SAMPLES:
            with self.subTest(sample=sample):
                root=self.fixture(sample);self.state(root,'synaptics_tcm2','coming')
                self.run_phase(root,'cache')
                cached=root/'tmp/dijun-runtime/modules/synaptics_tcm2.ko'
                self.assertTrue(cached.is_file())
                row=next(row.split() for row in (root/'tmp/dijun-runtime/modules.plan').read_text().splitlines() if row.startswith('synaptics_tcm2 '))
                self.assertEqual(sha(cached),row[1])

    def test_success_exit_without_live_module(self):
        root=self.fixture();self.run_phase(root,'cache')
        p=root/'mockbin/insmod'
        p.write_text(p.read_text().replace("(r/f'sys/module/{module}/initstate').write_text('live\\n')", "(r/f'sys/module/{module}/initstate').write_text('coming\\n' if module=='synaptics_tcm2' else 'live\\n')"))
        self.run_phase(root,'modules')
        self.assertEqual(self.props(root)['twrp.profile.touch_modules'],'failed')
        self.assertEqual(self.props(root)['twrp.profile.modules'],'partial')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--script',type=Path);parser.add_argument('--image',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert not (args.image and args.script)
    if args.image:
        sys.path.insert(0,str(ROOT/'scripts'))
        from firmware_facts import boot_parts,ramdisk_entries
        image=args.image.read_bytes();runtime.IMAGE_SHA=hashlib.sha256(image).hexdigest()
        runtime.IMAGE_ENTRIES={e[0]:e for e in ramdisk_entries(boot_parts(image)[1]['ramdisk'])}
        image_temp=tempfile.TemporaryDirectory(prefix='dijun-module-image-')
        runtime.IMAGE_CAS=Path(image_temp.name)
        for name,e in runtime.IMAGE_ENTRIES.items():
            if name.startswith('system/etc/dijun/blobs/') and stat.S_ISREG(e[1]):
                assert hashlib.sha256(e[-1]).hexdigest()==Path(name).name
                (runtime.IMAGE_CAS/Path(name).name).write_bytes(e[-1])
    names=['test_nonlive_hard_dependency','test_initializing_touch_lifecycle',
           'test_cache_retains_initializing_module_bytes','test_success_exit_without_live_module']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(States(n) for n in names))
    script=args.script or ROOT/'dtsrc/O1_asic_dual/profiles/runtime/dijun-runtime.sh'
    files=[script,Path(__file__).resolve(),ROOT/'tests/profile_runtime_test.py',ROOT/'tests/profile_selection_test.py']
    if args.image:files.remove(script)
    report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,
                failures=len(result.failures),errors=len(result.errors),cases=runtime.RESULTS,
                image_sha256=runtime.IMAGE_SHA,
                runtime_sha256=hashlib.sha256(runtime.IMAGE_ENTRIES['system/bin/dijun-runtime.sh'][-1]).hexdigest() if args.image else sha(script),
                tests={str(p):sha(p) for p in files},scope=__doc__.strip())
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
