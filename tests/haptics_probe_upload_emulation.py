#!/usr/bin/env python3
"""Join original OS4 probe/DT/power/PLL to stock upload and DSP configuration.

Properties are bound to original merged overlay evidence. Regulator/GPIO/pinctrl,
workqueue, remove and debugfs are explicit service fixtures. Stock algorithm rows
are supplied through regmap reads; PM/HALO/IRQ and all-FF sequence data remain
synthetic. All cases terminate in injected failures, never a successful DSP boot,
input registration, actual cleanup, IRQ scheduling or physical motor output.
"""
import json
from pathlib import Path
import subprocess
from haptics_config_emulation import Config, ROOT, DEPS, CTX, sha
from haptics_coefficients_emulation import table, bin_writes
from haptics_firmware_emulation import inventory
from haptics_driver_emulation import MASK, UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30, UC_ARM64_REG_SP


class ProbeUpload(Config):
    def __init__(self,path,blobs,properties):
        super().__init__(path,blobs,'cs40l26.wmfw')
        self.properties=properties;self.boundaries=[];self.removed=[];self.property_reads=[];self.probe_messages=[]
        self.service_results=dict(alloc_workqueue_noprof=0x4080000,devm_regulator_bulk_get=0,regulator_bulk_enable=0,
            devm_gpiod_get_optional=0x4088000,devm_pinctrl_get=0x4098000,pinctrl_lookup_state=0x40a0000,
            pinctrl_select_state=0)
        self.watch+=['cs40l26_probe','cs40l26_fw_upload','cs40l26_input_init','cs40l26_bst_dcm_config',
                     'cs40l26_bst_ipk_config','cs40l26_part_num_resolve','cs40l26_set_pll_loop']
        self.intercept('cs40l26_remove')
        # Probe starts with a zeroed context; original DT and chip resolver must
        # supply defaults, flags and ROM pointers. Do not retain upload fixtures.
        self.uc.mem_write(CTX,b'\0'*0x2000)
        self.put64(CTX,0x4060000);self.put64(CTX+8,0x4070000)

    def run(self,name,*args):
        if name!='cs40l26_probe':return super().run(name,*args)
        for i,value in enumerate(args):self.uc.reg_write(UC_ARM64_REG_X0+i,value&MASK)
        self.uc.reg_write(UC_ARM64_REG_SP,0x5020000-16)
        self.uc.reg_write(UC_ARM64_REG_X30,self.return_address)
        self.uc.emu_start(self.symbols[name],self.return_address,timeout=10000000,count=1000000)
        assert self.uc.reg_read(UC_ARM64_REG_PC)==self.return_address,('probe upload budget',name)
        value=self.arg(0)&0xffffffff
        return value if value<(1<<31) else value-(1<<32)

    def on_code(self,uc,address,size,data):
        if not hasattr(self,'service_results'):return super().on_code(uc,address,size,data)
        name=self.hooks.get(address)
        if name is None:return super().on_code(uc,address,size,data)
        a=[self.arg(i) for i in range(5)];result=None
        if name in self.service_results:result=self.service_results[name]
        elif name=='cs40l26_remove':self.removed.append(a[0]);result=0
        elif name in ['device_property_present','device_property_read_u32_array']:
            key=self.string(a[1]);value=self.properties.get(key)
            self.property_reads.append(dict(api=name,property=key,value=value))
            if name=='device_property_present':result=int(key in self.properties)
            elif value is None:result=-22
            else:
                assert isinstance(value,list) and all(isinstance(x,int) for x in value),(key,value)
                if not a[2]:result=len(value)
                elif len(value)<a[3]:result=-75
                else:
                    for i,x in enumerate(value[:a[3]]):self.put32(a[2]+4*i,x)
                    result=0
        elif name in ['device_get_child_node_count','device_get_next_child_node','fwnode_get_child_node_count',
                      '__mutex_init','timer_init_key','gpiod_set_value_cansleep','__init_swait_queue_head']:
            result=0
        elif name=='_printk':self.probe_messages.append(self.string(a[0]));result=0
        elif name=='__dev_fwnode_const':result=a[0]
        if result is None:return super().on_code(uc,address,size,data)
        self.boundaries.append(dict(name=name,args=a,result=result));self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


def exercise(path,blobs,properties):
    results=[]
    expected=inventory(blobs['cs40l26.wmfw'])['writes'][:]
    rows=table(blobs['cs40l26.wmfw'])[1]
    for name in ['cs40l26.bin','cs40l26-svc.bin','cs40l26-dvl.bin','cs40l26-a2h.bin','cs40l26-dbc.bin']:
        expected+=bin_writes(blobs[name],rows)
    labels=['request-missing','raw-first-error','CALL-RAM-exhausted','active-sequence-read-error',
            'sequence-first-write-error','HALO-invalid','GPIO-mask-read-error','boost-control-read-error']
    for label in labels:
        m=ProbeUpload(path,blobs,properties)
        if label=='request-missing':m.missing={'cs40l26.wmfw'}
        if label=='raw-first-error':m.raw_failure=1
        if label=='CALL-RAM-exhausted':m.failed_write_address=0x2800ff8
        if label=='active-sequence-read-error':m.rawread_failure=1
        if label=='sequence-first-write-error':m.bulk_failure=1
        if label=='HALO-invalid':m.hardware[0x2800fa8]=0
        if label=='GPIO-mask-read-error':m.read_errors[0x381c]=-5
        if label=='boost-control-read-error':
            m.hardware[0x381c]=0xffffffff;m.read_errors[0x3804]=-5
        rc=m.run('cs40l26_probe',CTX)
        assert rc==(-2 if label=='request-missing' else -62 if label=='CALL-RAM-exhausted' else -22 if label=='HALO-invalid' else -5)
        assert m.removed==[CTX] and 'cs40l26_input_init' not in m.entries
        assert m.entries[0]=='cs40l26_probe' and m.entries.count('cs40l26_fw_upload')==1
        assert 'cs40l26_set_pll_loop' in m.entries and 'cs40l26_part_num_resolve' in m.entries
        assert m.u64(CTX+0x1af8) and m.uc.mem_read(CTX+0x1c8,2)==b'\0\0'
        assert m.uc.mem_read(CTX+0x1cb,1)==b'\0'
        assert any(p['property']=='cirrus,f0-default' and p['value']==[130<<14] for p in m.property_reads)
        loaded=int.from_bytes(m.uc.mem_read(CTX+0x1ca,1),'little')
        assert loaded==int(label not in ['request-missing','raw-first-error','CALL-RAM-exhausted'])
        assert len(m.raw)==(0 if label=='request-missing' else 1 if label=='raw-first-error' else 68)
        assert m.raw==([] if label=='request-missing' else expected[:1] if label=='raw-first-error' else expected)
        if label=='request-missing':assert m.released==[0]
        else:assert m.released==[m.fwmap[n] for n in m.requests]
        if label=='boost-control-read-error':
            assert 'cs40l26_bst_ipk_config' in m.entries and m.reads[-1]['address']==0x3804
            assert len(m.bulk)==9
            assert any(w['address']==0x3808 and w['value']==0x40 for w in m.writes)
            assert any(w['address']==0x3800 and w['value']==0xaa for w in m.writes)
        print(label,rc,'loaded',loaded,'raw',len(m.raw),'bulk',len(m.bulk),flush=True)
        results.append(dict(case=label,status='PASS',result=rc,fw_loaded=loaded,entries=m.entries,
            properties_read=m.property_reads,service_boundaries=m.boundaries,remove_calls=m.removed,
            raw_writes=m.raw,raw_reads=m.rawreads,bulk_writes=m.bulk,register_reads=m.reads,
            writes=m.writes,updates=m.updates,requests=m.requests,released=m.released,messages=m.messages,
            probe_messages=m.probe_messages))
    return results


def main():
    dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text())
    prior=json.loads((ROOT/'logs/haptics-config-emulation.json').read_text())
    sources={str(dtpath.relative_to(ROOT)):sha(dtpath)};drivers={};cases=[]
    for field in ['sources','libfdt_sources']:
        for name,expected in dt[field].items():
            p=Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p)==expected;sources[str(p)]=expected
    for sample in ['os4-current','os4-stable']:
        record=prior['drivers'][sample];path=ROOT/record['path'];assert sha(path)==record['sha256'];drivers[sample]=record
        merged=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')
        node=merged['haptics']['/soc/i2c@EC100000/cs40l26@43'];assert node['active']
        files=sorted((ROOT/'firmware/samples'/sample/'analysis/odm/firmware').glob('cs40l26*'))
        sources.update({str(p.relative_to(ROOT)):sha(p) for p in files});blobs={p.name:p.read_bytes() for p in files}
        disasm=ROOT/'logs'/f'{sample}-haptics-probe-upload-core.disasm'
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump','-dr',
            '--disassemble-symbols=cs40l26_probe,cs40l26_fw_upload,cs40l26_dsp_config,cs40l26_gpio_config,cs40l26_bst_dcm_config,cs40l26_bst_ipk_config',str(path)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        cases.extend(dict(sample=sample,**c) for c in exercise(path,blobs,node['properties']))
    assert len(cases)==16
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in ['haptics_config_emulation.py',
        'haptics_coefficients_emulation.py','haptics_upload_emulation.py','haptics_firmware_emulation.py',
        'haptics_driver_emulation.py','haptics-emulator-dependencies.json']]+[ROOT/'scripts/firmware_facts.py']
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/haptics-probe-upload-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':main()
