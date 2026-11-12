#!/usr/bin/env python3
"""Join original OS4 probe/upload to runtime PM, logger and ASP failure paths.

Stock DT/firmware/algorithm tables and original ARM64 functions execute. Runtime
PM, timers/time, logger COUNT/SOURCE reads, all-FF sequences and regmap services
are explicit fixtures; writes never change supplied register values. COUNT=0
and SOURCE=0 are synthetic, not a DSP dump. Every scenario injects a failure;
no full probe/input, kernel PM scheduling, DSP execution or motor is claimed.
"""
import json
from pathlib import Path
import struct
import subprocess
from haptics_postboost_emulation import PostBoost, WATCH, ROOT, DEPS, CTX, sha
from haptics_coefficients_emulation import table, bin_writes
from haptics_firmware_emulation import inventory
from haptics_driver_emulation import MASK, UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30


class Runtime(PostBoost):
    def __init__(self,*args):
        self.pm_services=[];self.multi=[];self.pm_error=0;self.multi_error=0
        self.fail_logger_alloc=False;self.fail_asp_alloc=False
        super().__init__(*args)
        self.watch+=WATCH+['cs40l26_pm_runtime_setup','cs40l26_pm_enter','cs40l26_pm_exit',
                          'cs40l26_logger_setup','cs40l26_logger_src_add','cs40l26_asp_config']
        self.hardware.update({0x381c:0xffffffff,0x3804:0,0x7068:0,0x201c:0,0x6408:0,
                              0x6404:0,0x10114:0xffffffff,0x2805a34:0,0x2805a44:0})

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        a=[self.arg(i) for i in range(4)] if name else []
        if name=='_dev_alert':
            self.messages.append(self.string(a[1]));result=0
        elif name in ['__pm_runtime_use_autosuspend','pm_runtime_set_autosuspend_delay',
                    'pm_runtime_enable','mod_timer','ktime_get_with_offset',
                    '__pm_runtime_resume','__pm_runtime_suspend','__pm_runtime_set_status']:
            result=self.pm_error if name=='__pm_runtime_resume' else 0
            self.pm_services.append(dict(name=name,args=a,result=result))
        elif name=='devm_kmalloc' and self.fail_logger_alloc and 'cs40l26_logger_setup' in self.entries:
            assert a[1]==6
            result=0
        elif name=='__kmalloc_cache_noprof' and self.fail_asp_alloc and 'cs40l26_asp_config' in self.entries:
            assert a[2]==24
            result=0
        elif name=='regmap_multi_reg_write':
            assert a[2]==2
            raw=bytes(uc.mem_read(a[1],24))
            values=[list(struct.unpack_from('<III',raw,i)) for i in [0,12]]
            assert values==[[0x4c40,8,0],[0x4c50,9,0]]
            self.multi.append(dict(values=values,result=self.multi_error));result=self.multi_error
        else:return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


def exercise(path,blobs,properties):
    expected=inventory(blobs['cs40l26.wmfw'])['writes'][:]
    rows=table(blobs['cs40l26.wmfw'])[1]
    for n in ['cs40l26.bin','cs40l26-svc.bin','cs40l26-dvl.bin','cs40l26-a2h.bin','cs40l26-dbc.bin']:
        expected+=bin_writes(blobs[n],rows)
    results=[]
    for label in ['runtime-resume-error','logger-count-read','logger-source-read','logger-allocation',
                  'ASP-allocation','ASP-multi-write','ASP-first-sequence','ASP-second-sequence']:
        m=Runtime(path,blobs,properties)
        if label=='runtime-resume-error':m.pm_error=-5
        if label=='logger-count-read':m.read_errors[0x2805a34]=-5
        if label=='logger-source-read':m.read_errors[0x2805a44]=-5
        if label=='logger-allocation':m.fail_logger_alloc=True
        if label=='ASP-allocation':m.fail_asp_alloc=True
        if label=='ASP-multi-write':m.multi_error=-5
        if label=='ASP-first-sequence':m.bulk_failure=24
        if label=='ASP-second-sequence':m.bulk_failure=25
        rc=m.run('cs40l26_probe',CTX)
        assert rc==(-12 if label.endswith('allocation') else -5),(label,rc)
        assert m.raw==expected and len(m.raw)==68 and m.removed==[CTX]
        assert m.uc.mem_read(CTX+0x1ca,1)==b'\1' and 'cs40l26_input_init' not in m.entries
        assert m.released==[m.fwmap[n] for n in m.requests]
        names=[s['name'] for s in m.pm_services]
        assert names[:3]==['__pm_runtime_use_autosuspend','pm_runtime_set_autosuspend_delay','pm_runtime_enable']
        assert m.pm_services[0]['args'][:2]==[0x4060000,1]
        assert m.pm_services[1]['args'][:2]==[0x4060000,2000]
        assert names.count('__pm_runtime_resume')==1
        if label=='runtime-resume-error':
            assert 'cs40l26_logger_setup' not in m.entries and 'cs40l26_pm_exit' in m.entries
            assert names[-2:]==['__pm_runtime_set_status','__pm_runtime_suspend']
            assert m.pm_services[-2]['args'][:2]==[0x4060000,0]
        else:
            assert 'cs40l26_logger_setup' in m.entries and 'cs40l26_pm_exit' in m.entries
            assert names[-1]=='__pm_runtime_suspend'
        if label.startswith('ASP-'):
            assert 'cs40l26_asp_config' in m.entries and m.u32(CTX+0x1c08)==1
            assert any(w==dict(address=0x2805a34,value=1) for w in m.writes)
            assert any(w==dict(address=0x2805a44,value=13964937) for w in m.writes)
        else:assert 'cs40l26_asp_config' not in m.entries
        assert len(m.multi)==int(label in ['ASP-multi-write','ASP-first-sequence','ASP-second-sequence'])
        assert len(m.bulk)==(24 if label=='ASP-first-sequence' else 25 if label=='ASP-second-sequence' else 23)
        if label.startswith('logger-') and label.endswith('read'):
            assert m.reads[-1]['result']==-5
        # Coeff addresses must come from original parser/get_reg, not fixed output hooks.
        m.dsp=m.u64(CTX+0x50)
        coeff=[r for r in m.records() if r['algorithm']==0x4013d and r['name'] in ['COUNT','SOURCE']]
        assert {r['name']:r['register'] for r in coeff}=={'COUNT':0x2805a34,'SOURCE':0x2805a44}
        print(label,rc,'bulk',len(m.bulk),'pm-exit','cs40l26_pm_exit' in m.entries,flush=True)
        results.append(dict(case=label,status='PASS',result=rc,fw_loaded=1,entries=m.entries,
            pm_services=m.pm_services,multi_writes=m.multi,bulk_writes=m.bulk,raw_writes=m.raw,
            writes=m.writes,reads=m.reads,logger_count=m.u32(CTX+0x1c08),logger_coefficients=coeff,
            remove_calls=m.removed,messages=m.messages))
    return results


def main():
    dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text())
    sources={str(dtpath.relative_to(ROOT)):sha(dtpath)};cases=[];drivers={}
    for field in ['sources','libfdt_sources']:
        for name,expected in dt[field].items():
            p=Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p)==expected;sources[str(p)]=expected
    tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    for sample in ['os4-current','os4-stable']:
        base=ROOT/'firmware/samples'/sample/'analysis';path=base/'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        node=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']
        assert node['active']
        files=sorted((base/'odm/firmware').glob('cs40l26*'));blobs={p.name:p.read_bytes() for p in files}
        sources.update({str(p.relative_to(ROOT)):sha(p) for p in files})
        disasm=ROOT/'logs'/f'{sample}-haptics-runtime-config-core.disasm'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols=cs40l26_pm_runtime_setup,cs40l26_pm_enter,cs40l26_pm_exit,cs40l26_resume_error_handle,cs40l26_logger_setup,cs40l26_logger_src_add,cs40l26_asp_config,cs40l26_dsp_config',str(path)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        cases.extend(dict(sample=sample,**c) for c in exercise(path,blobs,node['properties']))
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in ['haptics_postboost_emulation.py',
        'haptics_probe_upload_emulation.py','haptics_config_emulation.py','haptics_coefficients_emulation.py',
        'haptics_upload_emulation.py','haptics_firmware_emulation.py','haptics_driver_emulation.py',
        'haptics-emulator-dependencies.json']]+[ROOT/'scripts/firmware_facts.py']
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/haptics-runtime-config-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':main()
