#!/usr/bin/env python3
"""Execute exact OS4 otapreopt scripts with delivered ARM64 shell and getprop.

Private ordinary-file chroot only. Native static command adapters explicitly
bridge shell exec to packaged getprop through QEMU, or supply named property
fixtures. ART/pm calls are rejected and recorded; no real Android property area,
Binder, mounts, original dexopt execution or complete OTA integration.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT.parent/'twrp'
sys.path.insert(0, str(ROOT/'scripts'))
from acquire_firmware import sha256_file, fields
from firmware_facts import boot_parts, ramdisk_entries


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


ADAPTER = r'''
#include <stdio.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char**argv){
 if(strstr(argv[0],"pm")){
   FILE*f=fopen("/work/art-called","w");if(f){fputs("unexpected ART call",f);fclose(f);}return 99;
 }
 if(argc!=2||strcmp(argv[1],"dev.bootcomplete"))return 98;
 FILE*f=fopen("/work/property-mode","r");char mode[32]={0};if(!f)return 97;
 if(!fgets(mode,sizeof(mode),f))return 96;fclose(f);
 f=fopen("/work/property-called","w");if(!f)return 95;fputs(mode,f);fclose(f);
 if(!strcmp(mode,"actual")){
  char*args[]={"/qemu","-L","/android","-E","LD_LIBRARY_PATH=/android/system/lib64",
   "/android/system/bin/linker64","/android/system/bin/toolbox","getprop",argv[1],0};
  execv("/qemu",args);return 94;
 }
 puts(mode);return 0;
}
'''


def main():
    index = json.loads((ROOT/'simulation-report.json').read_text())
    image = Path(index['image']); assert sha(image) == index['image_sha256']
    qemu = ROOT/'tools/qemu-user/qemu-aarch64'
    assert sha(qemu) == json.loads(qemu.with_name('source.json').read_text())['binary_sha256']
    sources = {str(p):sha(p) for p in [Path(__file__), ROOT/'scripts/acquire_firmware.py', ROOT/'scripts/firmware_facts.py']}
    samples = []
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT/'firmware/samples'/sample
        inv = json.loads((base/'inventory.json').read_text())
        system = base/'system.img'
        assert sha256_file(system) == inv['partitions']['system']['sha256']
        manifest = base/'payload-manifest.pb'; assert sha(manifest) == inv['manifest_sha256']
        configured = [dict(fields(v)) for k,v in fields(manifest.read_bytes()) if k == 13]
        partition = next(p for p in configured if p[1] == b'system')
        assert partition[2] == 1 and partition[9] == 1
        path = '/'+partition[3].decode()
        script = subprocess.check_output(['dump.erofs','--cat','--path='+path,str(system)])
        metadata = subprocess.check_output(['dump.erofs','--path='+path,str(system)],text=True)
        assert script.startswith(b'#!/system/bin/sh\n') and 'regular file' in metadata
        samples.append(dict(sample=sample, system_sha256=inv['partitions']['system']['sha256'],
            manifest_sha256=sha(manifest), path=path, script_sha256=hashlib.sha256(script).hexdigest(),
            script_size=len(script), metadata=metadata, script=script))
        sources[str(manifest)] = sha(manifest)
    dependencies = {str(qemu):sha(qemu), '/usr/bin/dump.erofs':sha('/usr/bin/dump.erofs')}
    cases = []; entries = {}
    with tempfile.TemporaryDirectory(prefix='ota-stock-postinstall-') as tmp:
        work = Path(tmp); jail = work/'jail'
        for name, mode, *rest in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk']):
            if stat.S_ISREG(mode) and (name in ['system/bin/linker64','system/bin/sh','system/bin/toolbox'] or
                (name.startswith('system/lib64/') and name.endswith('.so'))):
                dest = jail/'android'/name; dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(rest[-1]); dest.chmod(mode & 0o777)
                entries[name] = hashlib.sha256(rest[-1]).hexdigest()
        for binary in ['sh','toolbox']:
            content = (jail/'android/system/bin'/binary).read_bytes()
            assert content[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H',content,18)[0] == 183
        (jail/'qemu').write_bytes(qemu.read_bytes()); (jail/'qemu').chmod(0o755)
        (jail/'dev').mkdir(); (jail/'dev/null').touch()
        (jail/'fixture').mkdir()
        cfile = work/'adapter.c'; cfile.write_text(ADAPTER)
        compiler = shutil.which('cc'); assert compiler
        dependencies[str(Path(compiler).resolve())] = sha(compiler)
        command = [compiler,'-static','-O2',str(cfile),'-o',str(jail/'fixture/getprop')]
        subprocess.run(command,check=True,capture_output=True)
        shutil.copyfile(jail/'fixture/getprop',jail/'fixture/pm'); (jail/'fixture/pm').chmod(0o755)
        adapter_sha = sha(jail/'fixture/getprop')
        def isolate():
            os.chroot(jail); os.chdir('/')
        probe = subprocess.run(['/qemu','-L','/android','-E','LD_LIBRARY_PATH=/android/system/lib64',
            '/android/system/bin/linker64','/android/system/bin/toolbox','getprop','dev.bootcomplete'],
            preexec_fn=isolate,capture_output=True,text=True,timeout=15)
        assert probe.returncode == 0 and probe.stdout.strip() == ''
        actual_getprop_probe = dict(returncode=probe.returncode,stdout=probe.stdout,stderr=probe.stderr)
        for sample in samples:
            for label, property_value, slot in [('actual-property-area-absent','actual','1'),
                    ('boot-incomplete','0','1'), ('malformed-property','not-1','1'),
                    ('boot-complete-invalid-slot','1','invalid')]:
                shutil.rmtree(jail/'work',ignore_errors=True); (jail/'work').mkdir()
                (jail/'work/script').write_bytes(sample['script'])
                (jail/'work/property-mode').write_text(property_value)
                result = subprocess.run(['/qemu','-L','/android','-E','LD_LIBRARY_PATH=/android/system/lib64',
                    '-E','PATH=/fixture','/android/system/bin/linker64','/android/system/bin/sh',
                    '/work/script',slot,'3'], preexec_fn=isolate, capture_output=True,text=True,timeout=15)
                expected = 1 if slot == 'invalid' else 0
                marker = 'Unknown target slot invalid' if slot == 'invalid' else 'boot-complete not detected'
                checks = dict(returncode=result.returncode == expected, expected_output=marker in result.stdout,
                    property_read=(jail/'work/property-called').read_text() == property_value,
                    no_art_call=not (jail/'work/art-called').exists())
                cases.append(dict(sample=sample['sample'],name=label,status='PASS' if all(checks.values()) else 'FAIL',
                    checks=checks, returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        for sample in samples: del sample['script']
        report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,
            sources=sources,dependencies=dependencies,image=str(image),image_sha256=sha(image),image_entries=entries,
            samples=samples,cases=cases,actual_getprop_probe=actual_getprop_probe,adapter_sha256=adapter_sha,adapter_command=command,
            exact_stock_script=True,actual_arm64_shell=True,actual_getprop_missing_property_area=True,
            property_fixture_modes=['0','not-1','1'],art_executed=False,full_ota_install=False,
            production_fix=False,new_build=False)
        (ROOT/'logs/ota-stock-postinstall.json').write_text(json.dumps(report,indent=2)+'\n')
        print(report['status'],len(cases),'cases; no ART calls, no production change')
        return int(report['status'] != 'PASS')


if __name__ == '__main__':
    sys.exit(main())
