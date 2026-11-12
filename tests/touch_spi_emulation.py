#!/usr/bin/env python3
"""Execute stock OS4 SPI probe and Xiaomi DT parsing using original DTBO facts.

OF reads use hash-bound merged overlay properties. Kernel GPIO numbering,
pinctrl/regulator handles, core allocation, controller responses and panel/cdev
registration are fixtures. Separate platform probe is invoked explicitly after
SPI registration; its original hardware callbacks and CFI execute. No actual
SPI transfer, real power, kernel scheduling or phone.
"""
import json
from pathlib import Path
import struct
import subprocess

from touch_startup_emulation import Touch, LAYOUTS
from touch_configuration_emulation import Probe, CONFIG
from touch_startup_emulation import CTX, CORE, FW, INPUT
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

SPI, CONTROLLER, NODE, DEVICE = [0x4080000+i*0x10000 for i in range(4)]
PROPERTY, STRINGS = 0x40c0000, 0x40d0000


class Spi(Touch):
    def __init__(self, path, properties, children):
        super().__init__(path)
        self.properties=properties.copy()
        self.children={0x40e8000+i*0x100:props for i,props in enumerate(children.values())}
        self.boundaries, self.reads = [], []
        self.failures={}
        self.gpios={'synaptics,irq-gpio':76,'synaptics,reset-gpio':74}
        self.strings={}
        self.put64(SPI+0x3a0,CONTROLLER)
        self.put64(SPI+0x2f8,NODE)
        self.data=next(self.bases[i] for i,s in enumerate(self.sections) if s.name=='.data')
        self.bss=next(self.bases[i] for i,s in enumerate(self.sections) if s.name=='.bss')
        # Let the original Xiaomi DT parser populate these, instead of using
        # the inherited panel-success fixture's resolution/factor values.
        for offset in [0x1874,0x1878,0x18ac]:self.put32(self.bss+offset,0)

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        if name is None:return
        args=[self.arg(i) for i in range(6)]
        result=None
        if name in ['of_find_property','of_property_read_variable_u32_array',
                    'of_property_read_string','of_get_named_gpio']:
            assert args[0]==NODE or args[0] in self.children,('unknown node',name,args)
            props=self.properties if args[0]==NODE else self.children[args[0]]
            key=self.string(args[1]);raw=props.get(key)
            self.reads.append(dict(api=name,property=key))
            if name=='of_find_property':
                result=0 if raw is None else PROPERTY
                if raw is not None:self.put32(PROPERTY+8,len(raw) if isinstance(raw,bytes) else 12)
            elif name=='of_get_named_gpio':
                assert args[2]==0
                result=self.failures.get(key,self.gpios.get(key,-2))
            elif name=='of_property_read_string':
                if raw is None:result=-22
                else:
                    assert isinstance(raw,bytes) and raw.endswith(b'\0')
                    if key not in self.strings:
                        self.strings[key]=STRINGS+len(self.strings)*0x100
                        assert len(raw)<0x100
                        uc.mem_write(self.strings[key],raw)
                    self.put64(args[2],self.strings[key]);result=0
            else:
                if raw is None:result=-22
                else:
                    assert isinstance(raw,bytes) and len(raw)%4==0,key
                    count=len(raw)//4
                    if count<args[3]:result=-75
                    else:
                        count=min(count,args[4]) if args[4] else args[3]
                        uc.mem_write(args[2],struct.pack('<'+'I'*count,*struct.unpack('>'+'I'*count,raw[:count*4])))
                        result=count
            if name!='of_find_property' and key in self.failures:result=self.failures[key]
        elif name=='of_get_next_child':
            assert args[0]==NODE
            handles=list(self.children)
            result=(handles[0] if handles else 0) if args[1]==0 else (handles[handles.index(args[1])+1] if handles.index(args[1])+1<len(handles) else 0)
        elif name=='platform_device_alloc':
            assert self.string(args[0])=='synaptics_tcm' and args[1]==0
            result=self.failures.get(name,DEVICE)
        elif name=='devm_kmalloc':
            assert 0<args[1]<=0x10000
            result=self.alloc_cursor;self.alloc_cursor+=0x10000
            assert self.alloc_cursor<0x4200000
        elif name=='spi_setup':result=self.failures.get(name,0)
        elif name=='devm_pinctrl_get':result=self.failures.get(name,0x40e0000)
        elif name=='pinctrl_lookup_state':
            state=self.string(args[1])
            assert state in ['pmx_ts_active','pmx_ts_suspend','pmx_ts_secure','pmx_ts_nosecure']
            result=self.failures.get(state,0x40e1000)
        elif name=='pinctrl_select_state':result=self.failures.get(name,0)
        elif name=='devm_regulator_get':
            supply=self.string(args[1]);assert supply in ['avdd','iovdd']
            result=self.failures.get(supply,0x40f0000 if supply=='avdd' else 0x40f1000)
        elif name=='platform_device_add':
            assert args[0]==DEVICE
            # Registration result does not stand in for the platform driver's
            # separate syna_dev_probe; no automatic binding is simulated.
            assert self.u64(DEVICE+0xa0)==self.data+0x1d8
            result=self.failures.get(name,0)
        elif name in ['devm_pinctrl_put','devm_regulator_put','__mutex_init',
                      'xiaomi_touch_mievent_report_int','gpio_free']:
            result=0
        elif name in ['regulator_enable','regulator_disable']:
            assert args[0] in [0x40f0000,0x40f1000]
            result=self.failures.get((name,args[0]),0)
        elif name in ['msleep','usleep_range_state']:result=0
        elif name=='devm_gpio_request_one':
            result=self.failures.get((name,args[1]),0)
        elif name=='snprintf':
            assert args[1]<=128
            # This function only formats the GPIO diagnostic ownership label.
            label=('fixture-gpio-%d'%args[3]).encode()
            uc.mem_write(args[0],label[:args[1]-1]+b'\0');result=len(label)
        elif name=='gpio_to_desc':result=0x40e2000+args[0]*16
        elif name in ['gpiod_set_raw_value','gpiod_direction_output_raw','gpiod_direction_input']:
            result=0
        if result is None:return super().on_code(uc,address,size,data)
        self.boundaries.append(dict(name=name,args=args,result=result))
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


class Joined(Spi,Probe):
    """Share one original SPI-created hw object with the original platform probe.

    Python MRO retains explicit core allocation/controller/panel/cdev boundaries
    from Probe; the original static hardware function pointers and CFI execute.
    """
    def __init__(self,path,properties,children):
        super().__init__(path,properties,children)
        del self.hooks[self.symbols['syna_request_managed_device']]
        self.platform_phase=False

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        if self.platform_phase and name=='devm_kmalloc':
            return Probe.on_code(self,uc,address,size,data)
        return super().on_code(uc,address,size,data)


def exercise(path,properties,children):
    cases=[]
    for label,failures,expected in [
        ('original-DT-through-platform-registration',{},0),
        ('half-duplex-controller',{},-5),
        ('platform-allocation',{'platform_device_alloc':0},-12),
        ('spi-setup',{'spi_setup':-5},-5),
        ('pinctrl-defer-ignored',{'devm_pinctrl_get':-517},0),
        ('pinctrl-error-ignored',{'devm_pinctrl_get':-5},0),
        ('active-state-defer-ignored',{'pmx_ts_active':-517},0),
        ('suspend-state-error-ignored',{'pmx_ts_suspend':-5},0),
        ('secure-state-error-ignored',{'pmx_ts_secure':-5},0),
        ('nosecure-state-error-ignored',{'pmx_ts_nosecure':-5},0),
        ('active-select-error-ignored',{'pinctrl_select_state':-5},0),
        ('avdd-defer',{'avdd':-517},-517),
        ('iovdd-defer',{'iovdd':-517},-517),
        ('platform-registration-error',{'platform_device_add':-5},-5),
        ('irq-GPIO-defer-stored',{'synaptics,irq-gpio':-517},0),
        ('reset-GPIO-defer-stored',{'synaptics,reset-gpio':-517},0),
    ]:
        m=Spi(path,properties,children);m.failures=failures
        if label=='half-duplex-controller':m.uc.mem_write(CONTROLLER+0x3cc,b'\1\0')
        try: actual=m.run('syna_spi_probe',SPI)
        except Exception as error:
            raise AssertionError((label,m.calls[-12:])) from error
        assert actual==expected,(label,actual,expected,m.calls)
        names=[b['name'] for b in m.boundaries]
        added='platform_device_add' in names
        assert added==(expected==0 or label=='platform-registration-error'),(label,names)
        if expected==0:
            assert [m.u32(m.bss+i) for i in [0x1874,0x1878,0x18ac]]==[1440,3200,100]
            assert m.u32(m.data+0x230)==(failures.get('synaptics,irq-gpio',76)&0xffffffff)
            assert m.u32(m.data+0x270)==(failures.get('synaptics,reset-gpio',74)&0xffffffff)
            assert m.u32(m.data+0x1f4)==0 # Original DT SPI mode.
            assert m.string(m.u64(m.data+0x2a8))=='iovdd'
            assert m.string(m.u64(m.data+0x2b8))=='avdd'
        if label.startswith('pinctrl-') or '-state-' in label:
            assert m.u64(m.data+0x2c8)==0,(label,hex(m.u64(m.data+0x2c8)))
        if label=='active-select-error-ignored':assert m.u64(m.data+0x2c8)!=0
        assert 'syna_dev_probe' not in m.calls
        cases.append(dict(case=label,status='PASS',result=actual,
                          platform_registration_attempted=added,boundaries=m.boundaries,
                          properties_read=m.reads))
    for label,operation,failures,expected in [
        ('gpio-setup','syna_spi_config_gpios',{},0),
        ('irq-request-failure','syna_spi_config_gpios',{('devm_gpio_request_one',76):-16},-16),
        ('reset-request-failure','syna_spi_config_gpios',{('devm_gpio_request_one',74):-16},-16),
        ('power-on','syna_spi_power_on',{},0),
        ('avdd-enable-failure','syna_spi_power_on',{('regulator_enable',0x40f0000):-5},-5),
        ('iovdd-enable-failure','syna_spi_power_on',{('regulator_enable',0x40f1000):-5},-5),
        ('hardware-reset','syna_spi_hw_reset',{},0),
    ]:
        m=Spi(path,properties,children);assert m.run('syna_spi_probe',SPI)==0
        m.boundaries=[];m.failures=failures
        hw=m.data+0x1d8
        actual=m.run(operation,hw,0 if operation=='syna_spi_hw_reset' else 1)
        assert actual==expected,(label,actual,expected,m.calls[-20:])
        names=[b['name'] for b in m.boundaries]
        if label=='power-on':
            assert [b['args'][0] for b in m.boundaries if b['name']=='regulator_enable']==[0x40f0000,0x40f1000]
            assert [b['args'][0] for b in m.boundaries if b['name']=='msleep']==[50]
        if label=='hardware-reset':
            assert [b['args'][1] for b in m.boundaries if b['name']=='gpiod_set_raw_value']==[0,1]
            assert [b['args'][0] for b in m.boundaries if b['name']=='msleep']==[10,200]
        if label=='gpio-setup':
            assert [b['args'][1] for b in m.boundaries if b['name']=='devm_gpio_request_one']==[76,74]
        cases.append(dict(case=label,status='PASS',result=actual,boundaries=m.boundaries))
    return cases


def joined_exercise(path,properties,children):
    cases=[]
    for label,failures,expected in [
        ('joined-to-parser-ISR',{},0),
        ('joined-IRQ-request-failure',{('devm_gpio_request_one',76):-16},-16),
        ('joined-reset-request-failure',{('devm_gpio_request_one',74):-16},-16),
        ('joined-avdd-enable-failure',{('regulator_enable',0x40f0000):-5},-19),
        ('joined-iovdd-enable-failure',{('regulator_enable',0x40f1000):-5},-19),
        ('joined-configuration-timeout',{},0),
    ]:
        m=Joined(path,properties,children)
        assert m.run('syna_spi_probe',SPI)==0
        m.platform_phase=True;m.failures=failures;m.boundaries=[]
        if label=='joined-configuration-timeout':m.config_command_error=-110
        rc=m.run('syna_dev_probe',DEVICE)
        assert rc==expected,(label,rc,expected,m.calls[-30:])
        assert m.u64(CTX+0x300)==m.data+0x1d8
        assert not any(n in m.calls for n in ['fixture_power','fixture_setup','fixture_reset'])
        if label in ['joined-to-parser-ISR','joined-configuration-timeout']:
            assert m.queued
            assert m.run('syna_dev_reflash_startup_work',CTX+0x3d0)==0
            assert m.inputs and m.u64(CTX+0x3b8)==INPUT
            packet=FW+0x4000;m.uc.mem_write(packet,struct.pack('<BBHHBB',0,1,644,1589,7,6))
            m.put64(CTX+0x2c0,packet);m.put32(CTX+0x2cc,8)
            m.events=[]
            assert m.run('syna_dev_isr',0,CTX)==1
            if label=='joined-to-parser-ISR':
                assert m.u32(CORE+0x18c)==len(CONFIG)
                assert [INPUT,3,53,64400] in m.events and [INPUT,3,54,158900] in m.events
            else:
                assert m.u32(CORE+0x18c)==0 and not m.events
        else:assert not m.queued and not m.inputs
        cases.append(dict(case=label,status='PASS',result=rc,boundaries=m.boundaries,
                          controller_commands=[args[1] for args in m.commands],
                          input_registrations=m.inputs,events=m.events,
                          scope='SPI probe -> separate explicit platform bind -> original power/GPIO callbacks -> connect/configuration/background/parser/ISR; controller/panel/kernel remain fixtures.'))
    return cases


def main():
    evidence=ROOT/'logs/touch-devicetree-audit.json';dt=json.loads(evidence.read_text())
    assert dt['status']=='PASS'
    sources={str(evidence):sha(evidence)}
    for field in ['sources','tests','libfdt_sources']:
        for name,expected in dt[field].items():
            p=Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p)==expected; sources[str(p)]=expected
    drivers={};cases=[]
    tool=Path('/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump')
    for record in dt['cases']:
        sample=record['sample']
        children={name:{k:bytes.fromhex(v) for k,v in props.items()}
                  for name,props in record['touch_child_properties'].items()}
        assert list(children)==record['touch_child_nodes']
        properties={k:bytes.fromhex(v) if isinstance(v,str) else v
                    for k,v in record['canonical_touch_properties'].items()}
        path=ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        assert sha(path) in LAYOUTS
        drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        disasm=ROOT/'logs'/f'{sample}-touch-spi-probe.disasm'
        disasm.write_bytes(subprocess.check_output([str(tool),'-dr',
            '--disassemble-symbols=syna_spi_probe,xiaomi_parse_dt,syna_spi_request_gpio,syna_spi_config_gpios,syna_spi_power_on,syna_spi_hw_reset',str(path)]))
        sources[str(disasm)]=sha(disasm)
        for case in exercise(path,properties,children)+joined_exercise(path,properties,children):
            case['sample']=sample;cases.append(case)
        print('PASS',sample,len(cases)//len(drivers),'original SPI probe scenarios',flush=True)
    tests=[Path(__file__).resolve(),ROOT/'tests/touch_startup_emulation.py',ROOT/'tests/haptics_driver_emulation.py',ROOT/'tests/touch_configuration_emulation.py']
    dependencies=sorted(p for p in DEPS.rglob('*')
                        if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    report=dict(status='PASS',scope=__doc__.strip(),cases=cases,drivers=drivers,sources=sources,
                tests={str(p):sha(p) for p in tests},
                emulator_files={str(p):sha(p) for p in dependencies if p.exists()})
    (ROOT/'logs/touch-spi-emulation.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
