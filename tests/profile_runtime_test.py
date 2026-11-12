#!/usr/bin/env python3
"""Run shipped activation scripts with real OTA assets and substituted hardware.

Only mounts, properties, insmod and Binder services are substituted. No target
ELF is executed, no phone or host block device is touched. Nodes are private
null-device fixtures; all writes remain in TemporaryDirectory.
"""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from profile_selection_test import Selection, ROOT, TREE, CATALOG, BLOBS, SAMPLES

RESULTS = []
IMAGE_ENTRIES = {}
IMAGE_SHA = None
IMAGE_CAS = None
MOCK = r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
r=Path(os.environ['FIXTURE_ROOT']); name=Path(sys.argv[0]).name; args=sys.argv[1:]
p=r/'properties.json'; props=json.loads(p.read_text()) if p.exists() else {}
with (r/'calls.jsonl').open('a') as f:f.write(json.dumps([name,*args])+'\n')
if name == 'setprop':
    if os.environ.get('FAIL_START') and args==['ctl.start','dijun-keymint']:sys.exit(1)
    props[args[0]]=args[1]
elif name == 'resetprop':
    assert args[0]=='-n'
    if os.environ.get('FAIL_RESETPROP'):sys.exit(1)
    props[args[1]]=args[2]
elif name == 'getprop':print(props.get(args[0],''))
elif name == 'insmod':
    module=Path(args[0]).stem
    assert (r/'lib/firmware/cs40l26.wmfw').is_file(), 'firmware must precede insmod'
    assert not (r/f'sys/module/{module}').exists(), 'must not reinsert a loaded module'
    if module in ['xring_smartpa','xring_audio_hw_third']:
        # Prioritize the touch attempt, but a failed independent touch closure
        # must not manufacture a haptics insertion failure in this fixture.
        assert props.get('twrp.profile.touch_modules') in ['loaded','failed'], 'optional haptics must follow the touch attempt'
    if module == os.environ.get('FAIL_MODULE'):sys.exit(1)
    (r/f'sys/module/{module}').mkdir()
    (r/f'sys/module/{module}/initstate').write_text('live\n')
    if module in ['xring_smartpa','xring_audio_hw_third']:
        mode=os.environ.get('HAPTICS_INPUT','missing')
        target=r/'proc/bus/input/devices'
        if mode=='immediate':target.write_text('N: Name="cs40l26_input"\n')
        elif mode=='delayed':
            import subprocess
            subprocess.Popen([sys.executable,'-c',"import time,pathlib; time.sleep(.25); pathlib.Path(r'"+str(target)+"').write_text('N: Name=\\\"cs40l26_input\\\"\\n')"])
elif name == 'mount':
    assert args[:4]==['-t','ext4','-o','nosuid,nodev,noatime']
    assert args[-2:]==[str(r/'dev/block/by-name/persist'),str(r/'mnt/vendor/persist')]
    with (r/'proc/mounts').open('a') as f:f.write('/dev/block/persist-test /mnt/vendor/persist ext4 rw 0 0\n')
elif name == 'dijun-wait-services':
    calls=[json.loads(l) for l in (r/'calls.jsonl').read_text().splitlines()]
    assert all(['setprop','ctl.start',s] in calls for s in ['dijun-tee-supplicant','dijun-keymint','dijun-gatekeeper'])
    assert props.get('twrp.mitee.prepared')=='1'
    if os.environ.get('FAIL_BINDER'):sys.exit(1)
else:raise AssertionError(name)
p.write_text(json.dumps(props))
'''


class Runtime(unittest.TestCase):
    def fixture(self, sample='os4-current', slot='_a', preloaded=True):
        root = Selection.fixture(self, sample, slot)
        (root/'proc/bus/input').mkdir(parents=True)
        (root/'proc/bus/input/devices').write_text('')
        report = json.loads((CATALOG / sample / 'module-sources.json').read_text())
        for name, item in report['modules'].items():
            target = root / item['runtime'].lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / item['source'], target)
            if preloaded and item['runtime'].startswith('/lib/modules/'):
                (root / 'sys/module' / name).mkdir(parents=True, exist_ok=True)
                (root / 'sys/module' / name / 'initstate').write_text('live\n')
        (root / 'sys/module/firmware_class/parameters').mkdir(parents=True)
        (root / 'sys/module/firmware_class/parameters/path').write_text('original')
        for script in (TREE / 'profiles/runtime').glob('*.sh'):
            target = root / 'system/bin' / script.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(script, target)
            if IMAGE_ENTRIES:
                target.write_bytes(IMAGE_ENTRIES['system/bin/'+script.name][-1])
        catalog = root / 'system/etc/dijun/profiles'
        for sample_name in SAMPLES:
            (catalog / sample_name).mkdir(parents=True)
            for name in ['selection.conf','runtime-files.list','modules.plan','crypto.prop']:
                shutil.copy2(CATALOG / sample_name / name, catalog / sample_name / name)
                if IMAGE_ENTRIES:
                    (catalog / sample_name / name).write_bytes(IMAGE_ENTRIES[f'system/etc/dijun/profiles/{sample_name}/{name}'][-1])
        # Read-only shared CAS; tests never mutate it. Source assets are hashed.
        (root / 'system/etc/dijun/blobs').symlink_to(IMAGE_CAS or BLOBS, target_is_directory=True)
        (root / 'mockbin').mkdir()
        for name in ['setprop', 'getprop', 'resetprop', 'insmod', 'mount']:
            p = root / 'mockbin' / name
            p.write_text(MOCK); p.chmod(0o755)
        p = root / 'system/bin/dijun-wait-services'
        p.write_text(MOCK); p.chmod(0o755)
        (root / 'dev/block/by-name').mkdir(parents=True)
        (root / 'dev/block/persist-test').write_bytes(b'private fixture, not a block device')
        (root / 'dev/block/by-name/persist').symlink_to('../persist-test')
        for name in ['tee0','teepriv0']:
            os.mknod(root / 'dev' / name, stat.S_IFCHR | 0o600, os.makedev(1,3))
        return root

    def run_phase(self, root, phase, expected=0, **env):
        result = subprocess.run(['sh', str(root/'system/bin/dijun-runtime.sh'), phase,
                                 '--root', str(root)], capture_output=True, text=True,
                                env={**os.environ, 'PATH': str(root/'mockbin')+':'+os.environ['PATH'],
                                     'FIXTURE_ROOT': str(root), **env}, timeout=30)
        log = (root/'tmp/dijun-runtime.log').read_text()
        RESULTS.append(dict(phase=phase, expected=expected, actual=result.returncode,
                            sample=self.props(root).get('twrp.profile.selected'),
                            image_sha256=IMAGE_SHA,samples=SAMPLES,
                test_sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),ROOT/'tests/profile_selection_test.py']}, log=log, stderr=result.stderr))
        self.assertEqual(result.returncode, expected, result.stderr + log)
        return result

    def props(self, root): return json.loads((root/'properties.json').read_text())
    def calls(self, root): return [json.loads(l) for l in (root/'calls.jsonl').read_text().splitlines()]
    def unmount(self, root): (root/'proc/mounts').write_text('')

    def test_all_profiles_both_slots(self):
        for sample in SAMPLES:
            for slot in ['_a','_b']:
                with self.subTest(sample=sample, slot=slot):
                    root = self.fixture(sample, slot)
                    self.run_phase(root, 'cache')
                    self.assertFalse(any(c[0]=='insmod' or c[:2]==['setprop','ctl.start'] for c in self.calls(root)))
                    self.run_phase(root, 'modules')
                    self.unmount(root)
                    self.run_phase(root, 'publish')
                    self.assertEqual(self.props(root)['twrp.crypto.ready'],'1')
                    self.assertEqual(self.props(root)['twrp.profile.selected'],sample)
                    profile=json.loads((CATALOG/sample/'profile.json').read_text())
                    for path,item in profile['assets'].items():
                        if path.startswith(('odm/firmware/','system/etc/vintf/')):continue
                        p=root/path
                        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),item['sha256'],path)
                        self.assertEqual(stat.S_IMODE(p.stat().st_mode),int(item['mode'],8))
                    for key,value in profile['crypto_identity'].items():self.assertEqual(self.props(root)[key],value)

    def test_unloaded_dependency_order_and_no_reinsert(self):
        for sample in SAMPLES:
            with self.subTest(sample=sample):
                root=self.fixture(sample,preloaded=False)
                self.run_phase(root,'cache'); self.run_phase(root,'modules')
                report=json.loads((CATALOG/sample/'module-sources.json').read_text())
                loaded=[Path(c[1]).stem for c in self.calls(root) if c[0]=='insmod']
                self.assertEqual(loaded,report['order'])
                for name,item in report['modules'].items():
                    for dep in item['hard']:self.assertLess(loaded.index(dep),loaded.index(name))
                before=len(loaded); self.run_phase(root,'modules')
                self.assertEqual(len([c for c in self.calls(root) if c[0]=='insmod']),before)

    def test_bad_profile_and_module_abort_before_effects(self):
        for path in ['system_root/system/build.prop','vendor_dlkm/lib/modules/synaptics_tcm2.ko',
                     'vendor_dlkm/lib/modules/xring_audio_hw_third.ko']:
            root=self.fixture(); (root/path).write_bytes(b'wrong version')
            self.run_phase(root,'cache',1)
            self.assertFalse(any(c[0] in ['insmod','resetprop'] or c[:2]==['setprop','ctl.start'] for c in self.calls(root)))
            self.run_phase(root,'publish',1)
        root=self.fixture()
        report=json.loads((CATALOG/'os4-current/module-sources.json').read_text())
        source=next(i['runtime'] for n,i in report['modules'].items() if i['runtime'].startswith('/vendor_dlkm/') and n not in ['synaptics_tcm2','xring_audio_hw_third'])
        (root/source.lstrip('/')).unlink()
        self.run_phase(root,'cache',1)
        self.assertFalse(any(c[0]=='insmod' for c in self.calls(root)))

    def test_publish_mount_and_changed_cache_guards(self):
        root=self.fixture(); self.run_phase(root,'cache')
        self.run_phase(root,'publish',1)
        self.assertFalse(any(c[0]=='resetprop' for c in self.calls(root)))
        self.unmount(root)
        (root/'tmp/dijun-runtime/root/vendor/bin/tee-supplicant').write_bytes(b'changed')
        self.run_phase(root,'publish',1)
        self.assertFalse(any(c[:2]==['setprop','ctl.start'] for c in self.calls(root)))

    def test_service_failure_and_identity_failure(self):
        for failure in ['FAIL_BINDER','FAIL_RESETPROP','FAIL_START']:
            root=self.fixture(); self.run_phase(root,'cache'); self.unmount(root)
            self.run_phase(root,'publish',1,**{failure:'1'})
            self.assertEqual(self.props(root)['twrp.crypto.ready'],'0')
            if failure in ['FAIL_BINDER','FAIL_START']:
                self.assertEqual(len([c for c in self.calls(root) if c[:2]==['setprop','ctl.stop']]),3)
            else:self.assertFalse(any(c[:2]==['setprop','ctl.start'] for c in self.calls(root)))

    def test_optional_module_failure_preserves_crypto(self):
        for sample in SAMPLES:
            with self.subTest(sample=sample):
                root=self.fixture(sample); self.run_phase(root,'cache')
                plan=json.loads((CATALOG/sample/'module-sources.json').read_text())
                haptic=plan['roots'][1]
                self.run_phase(root,'modules',FAIL_MODULE=haptic)
                self.assertEqual(self.props(root)['twrp.profile.modules'],'partial')
                self.assertEqual(self.props(root)['twrp.profile.touch_modules'],'loaded')
                self.assertTrue((root/'sys/module/synaptics_tcm2').is_dir())
                self.unmount(root); self.run_phase(root,'publish')
                self.assertEqual(self.props(root)['twrp.crypto.ready'],'1')

    def test_touch_failure_and_preloaded_status(self):
        for preloaded in [False,True]:
            root=self.fixture('os4-stable')
            if preloaded:
                (root/'sys/module/synaptics_tcm2').mkdir()
                (root/'sys/module/synaptics_tcm2/initstate').write_text('live\n')
            self.run_phase(root,'cache')
            self.run_phase(root,'modules',FAIL_MODULE='synaptics_tcm2')
            self.assertEqual(self.props(root)['twrp.profile.touch_modules'],'loaded' if preloaded else 'failed')

    def test_haptics_input_registration_is_separate_from_module_live(self):
        for mode,expected in [('missing','not_registered'),('immediate','registered'),
                              ('delayed','registered')]:
            with self.subTest(mode=mode):
                root=self.fixture('os4-stable',preloaded=False)
                self.run_phase(root,'cache')
                self.run_phase(root,'modules',HAPTICS_INPUT=mode)
                self.assertEqual(self.props(root)['twrp.profile.haptics_input'],expected)
                self.assertEqual(self.props(root)['twrp.profile.touch_modules'],'loaded')
                self.unmount(root)

    def test_missing_tee_bounded_and_wrong_persist(self):
        for case in ['tee','persist']:
            root=self.fixture(); self.run_phase(root,'cache'); self.unmount(root)
            if case=='tee': (root/'dev/tee0').unlink()
            else:(root/'proc/mounts').write_text('/dev/block/other /mnt/vendor/persist ext4 rw 0 0\n')
            self.run_phase(root,'publish',1)
            self.assertFalse(any(c[:2]==['setprop','ctl.start'] for c in self.calls(root)))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--image',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.image:
        sys.path.insert(0,str(ROOT/'scripts'))
        from firmware_facts import boot_parts,ramdisk_entries
        image=args.image.read_bytes(); IMAGE_SHA=hashlib.sha256(image).hexdigest()
        IMAGE_ENTRIES={e[0]:e for e in ramdisk_entries(boot_parts(image)[1]['ramdisk'])}
        image_temp=tempfile.TemporaryDirectory(prefix='dijun-image-cas-')
        IMAGE_CAS=Path(image_temp.name)
        for path,entry in IMAGE_ENTRIES.items():
            if path.startswith('system/etc/dijun/blobs/') and stat.S_ISREG(entry[1]):
                sha=Path(path).name
                assert hashlib.sha256(entry[-1]).hexdigest()==sha
                (IMAGE_CAS/sha).write_bytes(entry[-1])
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Runtime))
    report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,
                cases=RESULTS,scope='Production activation shell, original OTA assets, fixture nodes/mounts/properties/insmod/Binder. No physical or TEE validation.',
                image_sha256=IMAGE_SHA,samples=SAMPLES,
                test_sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),ROOT/'tests/profile_selection_test.py']},
                sources={str(p.relative_to(ROOT)):hashlib.sha256(IMAGE_ENTRIES['system/bin/'+p.name][-1] if IMAGE_ENTRIES and p.suffix=='.sh' else p.read_bytes()).hexdigest()
                         for p in (TREE/'profiles/runtime').glob('*') if p.is_file()})
    dest='profile-runtime-image-test.json' if args.image else 'profile-runtime-test.json'
    (args.output or ROOT/'logs'/dest).write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
