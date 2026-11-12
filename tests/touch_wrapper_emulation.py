#!/usr/bin/env python3
"""Execute original OS4 Xiaomi wrapper panel/input/raw-mode entry points.

Panel parameter bytes are captured from original Synaptics setup with hash-bound
DT properties. Kernel allocations, proc creation, mode DT init, input core,
threads and notifier registration are explicit fixtures. Raw-mode callback
crosses an explicit host bridge into a separate original Synaptics emulator;
it does not emulate kernel linking or concurrent execution. No phone is used.
"""
import json
from pathlib import Path
import re
import subprocess

from touch_panel_emulation import Panel
from touch_startup_emulation import CTX, CORE
from haptics_driver_emulation import Module, ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

DEVICE, PARAMS, CALLBACKS, INPUT, TEXT = [0x4000000+i*0x10000 for i in range(5)]
WRAPPER_SHA='0ecca676ca633b18b325f3e2aa6708f280937442ca63a929191c6dd09076d5ad'


class Capture(Panel):
    def on_code(self,uc,address,size,data):
        if self.hooks.get(address)=='register_touch_panel':
            self.panel_bytes=bytes(uc.mem_read(self.arg(2),0xd6))
        super().on_code(uc,address,size,data)


class Wrapper(Module):
    def __init__(self,path,params,synaptics):
        assert sha(path)==WRAPPER_SHA
        super().__init__(path)
        self.synaptics=synaptics
        self.allocations=[];self.frees=[];self.axes=[];self.slots=[]
        self.input_allocations=0;self.input_registrations=0
        self.allocation_failures=set();self.workqueue_error=False
        self.input_allocate_error=False;self.input_register_error=0;self.slot_error=0
        self.mode_error=0;self.thread_error=0;self.shub_error=0
        self.callback_calls=[];self.queues=[];self.boundaries=[]
        self.bss=next(self.bases[i] for i,s in enumerate(self.sections) if s.name=='.bss')
        self.uc.mem_write(PARAMS,params)
        self.intercept('xiaomi_touch_create_proc')
        self.intercept('xiaomi_touch_init_touch_mode')
        for offset,name,signature in [(0x10,'fixture_lockdown',0x7bff871d),
                                       (0x70,'fixture_raw',0xcdde824b),
                                       (0x108,'fixture_temperature',0)]:
            address=0x300e000+offset*16
            self.put32(address-4,signature)
            self.hooks[address]=name;self.put64(CALLBACKS+offset,address)

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        if name is None:return
        args=[self.arg(i) for i in range(6)]
        if name in ['memcpy','memset']:
            assert args[2]<=0x10000
            payload=bytes([args[1]&255])*args[2] if name=='memset' else bytes(uc.mem_read(args[1],args[2]))
            if payload:uc.mem_write(args[0],payload)
            result=args[0]
        elif name in ['__kmalloc_noprof','__kmalloc_cache_noprof']:
            length=args[0] if name=='__kmalloc_noprof' else args[2]
            self.allocations.append(length)
            assert 0<length<=0x40000,(name,args)
            if len(self.allocations) in self.allocation_failures:result=0
            else:
                result=self.alloc_cursor;self.alloc_cursor+=(length+4095)&~4095
                assert self.alloc_cursor<0x4200000
                uc.mem_write(result,b'\0'*length)
        elif name=='input_allocate_device':
            self.input_allocations+=1;result=0 if self.input_allocate_error else INPUT
        elif name=='input_free_device':self.frees.append(args[0]);result=0
        elif name=='input_mt_init_slots':self.slots.append(args[:3]);result=self.slot_error
        elif name=='input_set_abs_params':self.axes.append(args);result=0
        elif name=='input_register_device':self.input_registrations+=1;result=self.input_register_error
        elif name=='snprintf':
            fmt=self.string(args[2]);assert fmt.count('%d')==1
            value=(fmt%args[3]).encode();assert len(value)<args[1]
            uc.mem_write(args[0],value+b'\0');result=len(value)
        elif name=='sscanf':
            assert self.string(args[1])=='%d'
            value=re.match(r'\s*([+-]?[0-9]+)',self.string(args[0]))
            if value:self.put32(args[2],int(value[1]))
            result=1 if value else (-1 if not self.string(args[0]).strip() else 0)
        elif name=='alloc_workqueue_noprof':result=0 if self.workqueue_error else 0x40f0000
        elif name=='xiaomi_touch_init_touch_mode':result=self.mode_error
        elif name=='kthread_create_on_node':result=self.thread_error or 0x40e0000
        elif name=='sh_register_recv_notifier':result=self.shub_error
        elif name=='fixture_lockdown':
            uc.mem_write(args[0],bytes([0x53,0x42,0x32,0x30,0x4f,2,0x72,0]));result=0
        elif name=='fixture_raw':
            value=args[0]&0xffffffff
            result=self.synaptics.run('syna_tcm_enable_touch_raw',value)
            self.callback_calls.append(dict(value=value,result=result))
        elif name=='queue_delayed_work_on':self.queues.append(args[:4]);result=1
        elif name in ['_printk','__mutex_init','__init_waitqueue_head','wake_up_process','kthread_stop',
                      'xiaomi_touch_create_proc','timer_init_key']:
            result=0
        else:raise AssertionError(('unknown wrapper boundary',name,args))
        self.calls.append(name);self.boundaries.append(dict(name=name,args=args,result=result))
        uc.reg_write(UC_ARM64_REG_X0,result&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))

    def panel(self):return self.run('register_touch_panel',DEVICE,0,PARAMS,CALLBACKS)

    def pointer(self,name,*args):
        self.run(name,*args)
        return self.arg(0)


def exercise(path,syna_path,properties,children):
    capture=Capture(syna_path,properties,children)
    capture.run('syna_xiaomi_touch_probe',CTX)
    params=capture.panel_bytes
    def fresh():return Wrapper(path,params,Capture(syna_path,properties,children))
    cases=[]
    def passed(label,m,**details):cases.append(dict(case=label,status='PASS',
        boundaries=m.boundaries,input_registrations=m.input_registrations,
        panel_mask=bytes(m.uc.mem_read(m.bss+0xa,1)).hex(),**details))
    for label in ['normal','duplicate','invalid-id','null-params','frame-allocation',
                  'raw-allocation','workqueue','all-cache-allocations','mode-error-ignored',
                  'thread-error-after-mask','shub-error-ignored']:
        m=fresh()
        if label=='frame-allocation':m.allocation_failures={1,2,3}
        if label=='raw-allocation':m.allocation_failures={2,3,4}
        if label=='workqueue':m.workqueue_error=True
        if label=='all-cache-allocations':m.allocation_failures={3,4,5}
        if label=='mode-error-ignored':m.mode_error=-1
        if label=='thread-error-after-mask':m.thread_error=-12
        if label=='shub-error-ignored':m.shub_error=-5
        if label=='invalid-id':rc=m.run('register_touch_panel',DEVICE,2,PARAMS,CALLBACKS)
        elif label=='null-params':rc=m.run('register_touch_panel',DEVICE,0,0,CALLBACKS)
        else:rc=m.panel()
        failed=label in ['invalid-id','null-params','frame-allocation','raw-allocation','workqueue','all-cache-allocations']
        assert (rc<0)==failed,(label,rc,m.allocations,m.calls)
        assert bool(bytes(m.uc.mem_read(m.bss+0xa,1))[0]&1)==(not failed)
        assert not m.input_allocations and not m.input_registrations
        if label=='duplicate':assert m.panel()==-1
        passed('panel-'+label,m,result=rc,allocations=m.allocations)
    for label in ['normal','without-panel','invalid-id','allocation-fails','registration-fails',
                  'slots-fail-ignored','shared-page-fails','duplicate']:
        m=fresh()
        if label not in ['without-panel','invalid-id']:assert m.panel()==0
        if label=='allocation-fails':m.input_allocate_error=True
        if label=='registration-fails':m.input_register_error=-12
        if label=='slots-fail-ignored':m.slot_error=-12
        if label=='shared-page-fails':m.allocation_failures.update(range(len(m.allocations)+1,len(m.allocations)+4))
        ptr=m.pointer('register_xiaomi_input_dev',2 if label=='invalid-id' else 0,143999,319999,64)
        failed=label in ['invalid-id','allocation-fails','registration-fails']
        assert ptr==(0 if failed else INPUT),(label,hex(ptr),m.calls)
        if label=='registration-fails':assert m.frees==[INPUT]
        if not failed:
            assert m.axes[:2]==[[INPUT,53,0,143999,0,0],[INPUT,54,0,319999,0,0]]
            assert m.slots==[[INPUT,10,2]]
            if label=='duplicate':assert m.pointer('register_xiaomi_input_dev',0,1,1,1)==INPUT and m.input_registrations==1
        passed('input-'+label,m,pointer=ptr,axes=m.axes)
    for label,payload,errors in [('disable',b'0\n',[0,0]),('enable',b'1\n',[0,0]),
                                 ('callback-error-hidden',b'0\n',[-110,-110]),
                                 ('invalid-text',b'abc',[0,0]),('empty',b'',[0,0]),
                                 ('without-panel',b'0\n',[0,0])]:
        m=fresh()
        if label!='without-panel':assert m.panel()==0
        m.synaptics.report_results=errors.copy()
        m.uc.mem_write(TEXT,payload+b'\0')
        rc=m.run('store_enable_touch_raw',DEVICE,0,TEXT,len(payload))
        assert rc==(-22 if label=='empty' else len(payload)),(label,rc)
        if label in ['empty','without-panel']:assert not m.callback_calls
        else:
            expected=1 if label=='enable' else 0
            assert m.callback_calls==[dict(value=expected,result=errors[1])]
            assert m.synaptics.reports==([[CORE,0x11,0],[CORE,0xc0,1]] if expected else [[CORE,0xc0,0],[CORE,0x11,1]])
        passed('raw-'+label,m,result=rc,callbacks=m.callback_calls,reports=m.synaptics.reports)
    return cases


def main():
    evidence=ROOT/'logs/touch-devicetree-audit.json';dt=json.loads(evidence.read_text())
    sources={str(evidence):sha(evidence)}
    for field in ['sources','tests','libfdt_sources']:
        for name,expected in dt[field].items():
            p=Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p)==expected;sources[str(p)]=expected
    cases=[];drivers={}
    tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    for record in dt['cases']:
        sample=record['sample'];base=ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules'
        path=base/'xiaomi_touch_dijun.ko';syna=base/'synaptics_tcm2.ko'
        for kind,p in [('wrapper',path),('synaptics',syna)]:drivers[sample+'-'+kind]=dict(path=str(p.relative_to(ROOT)),sha256=sha(p))
        properties={k:bytes.fromhex(v) if isinstance(v,str) else v for k,v in record['canonical_touch_properties'].items()}
        children={n:{k:bytes.fromhex(v) for k,v in p.items()} for n,p in record['touch_child_properties'].items()}
        disasm=ROOT/'logs'/f'{sample}-touch-wrapper-core.disasm'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols=register_touch_panel,register_xiaomi_input_dev,store_enable_touch_raw,get_xiaomi_touch_driver_param,kzalloc_retry',str(path)]))
        sources[str(disasm)]=sha(disasm)
        results=exercise(path,syna,properties,children)
        for case in results:case['sample']=sample;cases.append(case)
        print('PASS',sample,len(results),'wrapper cases',flush=True)
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/name for name in ['touch_panel_emulation.py','touch_transport_emulation.py',
        'touch_spi_emulation.py','touch_configuration_emulation.py','touch_startup_emulation.py','haptics_driver_emulation.py']]
    dependencies=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-wrapper-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p):sha(p) for p in tests},
        emulator_files={str(p):sha(p) for p in dependencies}),indent=2)+'\n')


if __name__=='__main__':main()
