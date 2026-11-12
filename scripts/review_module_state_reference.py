#!/usr/bin/env python3
"""Review upstream module-state semantics and bind existing current shell tests.

Executes the original v6.6 show_initstate leaf with a host structure/sysfs
fixture; inspects original load/sysfs ordering. Six original kernel byte-string
checks are interface corroboration only. No downstream loader, kernel module
init, asynchronous probe, device input, DSP or motor is executed.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from nested_partition_path_test import method
from firmware_facts import boot_parts

REFERENCES={
    'logs/linux-v6.6-module-main.c':'1698bcd686cc75e2724c82f8b952599dbdc0e4086fe8151b58606676a0d3b98c',
    'logs/linux-v6.6-module-sysfs.c':'e3da049c10035c6f1552085370f9f0afce484df4a14684b274e4b6868325da3e',
}

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def path(name):
    p=Path(name);return p if p.is_absolute() else ROOT/p

def main():
    index=json.loads((ROOT/'simulation-report.json').read_text())
    sources=[Path(__file__).resolve(),ROOT/'tests/nested_partition_path_test.py',
             ROOT/'scripts/firmware_facts.py',ROOT/'scripts/acquire_firmware.py']
    for name,expected in REFERENCES.items():assert sha(ROOT/name)==expected; sources.append(ROOT/name)
    main=(ROOT/'logs/linux-v6.6-module-main.c').read_text()
    sysfs=(ROOT/'logs/linux-v6.6-module-sysfs.c').read_text()
    load=method(main,'static int load_module(')
    init=method(main,'static noinline int do_init_module(')
    setup=method(sysfs,'int mod_sysfs_setup(')
    sysinit=method(sysfs,'static int mod_sysfs_init(')
    formation=method(main,'static int complete_formation(')
    # These are static ordering claims about the pinned reference, not an execution trace.
    ordering={
        'coming_before_sysfs':load.index('complete_formation(mod, info)')<load.index('mod_sysfs_setup(mod'),
        'sysfs_before_init':load.index('mod_sysfs_setup(mod')<load.index('return do_init_module(mod)'),
        'init_before_live':init.index('do_one_initcall(mod->init)')<init.index('mod->state = MODULE_STATE_LIVE'),
        'kobject_before_attributes':setup.index('mod_sysfs_init(mod)')<setup.index('module_add_modinfo_attrs(mod)'),
        'kobject_published': 'kobject_init_and_add(&mod->mkobj.kobj' in sysinit,
        'coming_assignment':'mod->state = MODULE_STATE_COMING' in formation,
        'readable_initstate_attribute':'__ATTR(initstate, 0444, show_initstate, NULL)' in main,
    }
    assert all(ordering.values()),ordering
    leaf=method(main,'static ssize_t show_initstate(')
    harness=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/types.h>
enum {MODULE_STATE_LIVE=0,MODULE_STATE_COMING=1,MODULE_STATE_GOING=2};
struct module {int state;};
struct module_attribute {int unused;};
struct module_kobject {struct module* mod;};
#define BUG() abort()
// ORIGINAL
int main(){
 const char*expected[]={"live\n","coming\n","going\n"};
 for(int state=0;state<3;++state){
  struct module mod={state};struct module_kobject mk={&mod};char output[32];
  ssize_t size=show_initstate(NULL,&mk,output);
  assert(size==(ssize_t)strlen(expected[state]) && strcmp(output,expected[state])==0);
  printf("state=%d output=%s",state,output);
 }
}
'''.replace('// ORIGINAL',leaf)
    with tempfile.TemporaryDirectory(prefix='module-state-reference-') as temp:
        p=Path(temp);(p/'test.c').write_text(harness)
        subprocess.run(['gcc','-std=c11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',
                        str(p/'test.c'),'-o',str(p/'test')],check=True)
        executed=subprocess.run([str(p/'test')],capture_output=True,text=True,timeout=5)
        assert executed.returncode==0,executed.stdout+executed.stderr
    evidence_path=ROOT/'logs/module-initstate-kernel-evidence.json'
    evidence=json.loads(evidence_path.read_text());sources.append(evidence_path)
    kernels=[]
    for row in evidence['cases']:
        image=ROOT/'firmware/samples'/row['sample']/'boot.img'
        assert sha(image)==row['boot_sha256']
        _,parts=boot_parts(image.read_bytes());kernel=parts['kernel']
        assert hashlib.sha256(kernel).hexdigest()==row['kernel_sha256']
        offsets={}
        for name,offset in row['strings'].items():
            assert kernel.find(name.encode()+b'\0')==offset,(row['sample'],name)
            offsets[name]=offset
        kernels.append(dict(sample=row['sample'],status='PASS',strings=offsets))
        sources.append(image)
    assert {r['sample'] for r in kernels}=={'os2-initial','os2-final','os3-initial','os3-final','os4-current','os4-stable'}
    current_entry=next(c for c in index['checks'] if c['name']=='module-initialization-lifecycle')
    before_entry=index['module_state_before_fix']
    reports=[]
    for entry,expected in [(current_entry,'PASS'),(before_entry,'FAIL')]:
        p=path(entry['evidence']);assert sha(p)==entry['evidence_sha256']
        report=json.loads(p.read_text());reports.append(report)
        assert report['status']==expected and report['tests_run']==4 and len(report['cases'])==24
        assert report['errors']==0
        assert report['failures']==(0 if expected=='PASS' else 14)
        for name,digest in report['tests'].items():assert sha(path(name))==digest; sources.append(path(name))
        sources.append(p)
    image=path(index['image']);assert sha(image)==index['image_sha256']==reports[0]['image_sha256']
    _,parts=boot_parts(image.read_bytes())
    from firmware_facts import ramdisk_entries
    scripts=[e[-1] for e in ramdisk_entries(parts['ramdisk']) if e[0]=='system/bin/dijun-runtime.sh']
    assert len(scripts)==1 and hashlib.sha256(scripts[0]).hexdigest()==reports[0]['runtime_sha256']
    archived=ROOT/'backups/module-state-pre-fix/dijun-runtime.sh'
    assert sha(archived)==reports[1]['runtime_sha256']
    normalized=lambda report:{str(path(n)):h for n,h in report['tests'].items() if path(n)!=archived}
    assert normalized(reports[0])==normalized(reports[1])
    sources.append(image)
    result=dict(status='PASS',scope=__doc__,image_sha256=index['image_sha256'],
                reference_version='Linux v6.6 upstream; not claimed equivalent to vendor kernels',
                static_ordering_checks=ordering,executed_show_initstate=dict(returncode=executed.returncode,
                    stdout=executed.stdout,stderr=executed.stderr,cases=3),kernel_interfaces=kernels,
                current_shell_tests=dict(tests_run=4,stage_calls=24,failures=0,
                    report=current_entry['evidence']),
                original_shell_control=dict(tests_run=4,stage_calls=24,failures=14,
                    report=before_entry['evidence']),
                historical_review='logs/module-state-review.json is retained unchanged as a historical record',
                sources={str(p):sha(p) for p in sorted(set(sources))})
    output=ROOT/'logs/module-state-reference-current.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: pinned upstream ordering7/state leaf3, six stock kernel interfaces, current shell4/24 and old14 failures; no downstream kernel/hardware execution.')

if __name__=='__main__':main()
