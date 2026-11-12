#!/usr/bin/env python3
"""Execute original probe through DT parsing/power/reset, ending before PLL I/O.

DT properties come from the separately hash-bound original overlay-5 merge.
Regulator/GPIO/pinctrl/workqueue services and remove are explicit fixtures.
PLL always fails: DSP boot, IRQ, cleanup internals and physical timing excluded.
"""
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from haptics_lifecycle_emulation import Lifecycle, CTX
from haptics_driver_emulation import ROOT, DEPS, LAYOUTS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30
from firmware_facts import haptics_module
from audit_haptics_devicetree import nodes, DTC_SOURCE, LIB_FILES, value


class Probe(Lifecycle):
    def __init__(self, path, properties):
        super().__init__(path)
        self.properties = properties
        self.boundaries = []
        self.reads = []
        self.removed = []
        self.intercept('cs40l26_remove')
        self.intercept('cs40l26_set_pll_loop')
        # These are allocated fixture handles, never Linux device pointers.
        self.results = dict(alloc_workqueue=0x4070000, alloc_workqueue_noprof=0x4070000,
                            devm_regulator_bulk_get=0, regulator_bulk_enable=0,
                            devm_gpiod_get_optional=0x4080000, devm_pinctrl_get=0x4090000,
                            pinctrl_lookup_state=0x40a0000, pinctrl_select_state=0,
                            cs40l26_set_pll_loop=-5)

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        args = [self.arg(i) for i in range(5)]
        result = None
        if name in self.results:
            self.boundaries.append(dict(name=name,args=args))
            result = self.results[name]
        elif name == 'cs40l26_remove':
            self.removed.append(args[0]); result = 0
        elif name in ('device_property_present','device_property_read_u32_array'):
            key = self.string(args[1])
            value = self.properties.get(key)
            self.reads.append(dict(api=name,property=key,value=value))
            if name == 'device_property_present': result = int(key in self.properties)
            elif value is None: result = -22
            else:
                assert isinstance(value,list) and all(isinstance(v,int) for v in value), key
                if args[2] == 0: result = len(value)
                elif len(value) < args[3]: result = -75
                else:
                    for i,v in enumerate(value[:args[3]]): self.put32(args[2]+4*i,v)
                    result = 0
        elif name in ('device_get_child_node_count','device_get_next_child_node',
                      'fwnode_get_child_node_count'):
            # Original merged CS40L26 node has no child nodes.
            result = 0
        elif name == '__dev_fwnode_const': result = args[0]
        elif name in ('__mutex_init','_printk','_dev_info','_dev_warn','timer_setup',
                      'init_timer_key','timer_init_key','hrtimer_init'):
            result = 0
        elif name in ('usleep_range_state','gpiod_set_value_cansleep'):
            self.boundaries.append(dict(name=name,args=args[:3])); result = 0
        if result is None: return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result & MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


def exercise(path, properties):
    cases=[]
    ordered=['workqueue','devm_regulator_bulk_get','regulator_bulk_enable',
             'devm_gpiod_get_optional','devm_pinctrl_get','pinctrl_lookup_state',
             'pinctrl_select_state','usleep_range_state','gpiod_set_value_cansleep',
             'usleep_range_state','cs40l26_set_pll_loop']
    for label,operation,failure,expected in [
        ('workqueue','alloc_workqueue',0,-12),
        ('regulator-get','devm_regulator_bulk_get',-517,-517),
        ('regulator-enable','regulator_bulk_enable',-5,-5),
        ('reset-gpio','devm_gpiod_get_optional',-517,-517),
        ('pinctrl-defer','devm_pinctrl_get',-517,0),
        ('pinctrl-error','devm_pinctrl_get',-5,-22),
        ('default-state-error','pinctrl_lookup_state',-5,0),
        ('select-state-error','pinctrl_select_state',-5,-5),
        ('reset-sequence-to-PLL-failure','cs40l26_set_pll_loop',-5,-5),
    ]:
        m=Probe(path,properties)
        if label=='workqueue':
            m.results['alloc_workqueue']=m.results['alloc_workqueue_noprof']=0
        else: m.results[operation]=failure
        actual=m.run('cs40l26_probe',CTX)
        assert actual==expected,(label,actual,expected,m.calls,m.messages)
        assert not m.registered and 'input_register_device' not in m.calls
        names=[b['name'] for b in m.boundaries]
        canonical=['workqueue' if n in ('alloc_workqueue','alloc_workqueue_noprof') else n for n in names]
        endpoint='workqueue' if label=='workqueue' else operation
        assert canonical==ordered[:ordered.index(endpoint)+1],(label,canonical)
        if label=='reset-sequence-to-PLL-failure':
            assert names[-4:]==['usleep_range_state','gpiod_set_value_cansleep',
                               'usleep_range_state','cs40l26_set_pll_loop'],names
            assert m.boundaries[-4]['args']==[1500,1600,2]
            assert m.boundaries[-3]['args'][:2]==[0x4080000,0]
            assert m.boundaries[-2]['args']==[6000,6100,2]
            flags=CTX+(0x1c8 if m.modern else 0x220)
            assert bytes(m.uc.mem_read(flags,2))==b'\0\0'
            assert any(r['property']=='cirrus,f0-default' and r['value']==[130<<14] for r in m.reads)
        else: assert 'cs40l26_set_pll_loop' not in names
        # A nondeferred pinctrl-get error exits directly; others call remove.
        assert m.removed==([] if label=='pinctrl-error' else [CTX]),(label,m.removed)
        cases.append(dict(case=label,status='PASS',result=actual,boundaries=m.boundaries,
                          properties_read=m.reads,remove_calls=m.removed))
    return cases


def main():
    dtpath=ROOT/'logs/haptics-devicetree-audit.json'
    dt=json.loads(dtpath.read_text()); assert dt['status']=='PASS'
    # Bind the archive inputs behind the merged properties, not only the JSON.
    for name,expected in dt['sources'].items(): assert sha(Path(name) if Path(name).is_absolute() else ROOT/name)==expected
    for name,expected in dt['libfdt_sources'].items(): assert sha(Path(name))==expected
    # Reconstruct only overlay 5 to verify the properties AND zero child nodes.
    with tempfile.TemporaryDirectory(prefix='dijun-probe-dt-') as temporary:
        temp=Path(temporary); exe=temp/'fdtoverlay'
        (temp/'version_gen.h').write_text('#define DTC_VERSION "dijun-host-evidence"\n')
        files=[DTC_SOURCE/'fdtoverlay.c',DTC_SOURCE/'util.c']+[DTC_SOURCE/'libfdt'/n for n in LIB_FILES]
        subprocess.run(['gcc','-O2','-D_GNU_SOURCE','-I'+str(temp),'-I'+str(DTC_SOURCE/'libfdt'),
                        *map(str,files),'-o',str(exe)],check=True)
        for merged in [c for c in dt['cases'] if c['case']=='overlay-5']:
            sample=ROOT/'firmware/samples'/merged['sample']
            blob=(sample/'dtbo.img').read_bytes()
            entry_offset=struct.unpack_from('>I',blob,20)[0]+5*32
            length,offset=struct.unpack_from('>II',blob,entry_offset)
            (temp/'overlay').write_bytes(blob[offset:offset+length])
            subprocess.run([str(exe),'-i',str(sample/'analysis/vendor_boot/dtb'),
                            '-o',str(temp/'merged'),str(temp/'overlay')],check=True,capture_output=True)
            assert sha(temp/'merged')==merged['merged_sha256']
            tree=nodes((temp/'merged').read_bytes()); node='/soc/i2c@EC100000/cs40l26@43'
            assert not any(p.startswith(node+'/') for p in tree)
            assert {k:value(v) for k,v in tree[node].items()}==merged['haptics'][node]['properties']
    cases,drivers=[],{}
    for sample in sorted({c['sample'] for c in dt['cases']}):
        merged=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')
        node=merged['haptics']['/soc/i2c@EC100000/cs40l26@43']
        assert node['active'] and node['properties']['bind-product']==['dijun']
        assert not node['driver_fw_defer'] and not node['rom_only']
        analysis=ROOT/'firmware/samples'/sample/'analysis'
        path=analysis/haptics_module(json.loads((analysis/'facts.json').read_text()))[0]
        assert sha(path) in LAYOUTS
        current=exercise(path,node['properties'])
        cases.extend(dict(sample=sample,**c) for c in current)
        drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        print('PASS',sample,len(current),'cases',flush=True)
    tests=[Path(__file__).resolve(),ROOT/'tests/haptics_lifecycle_emulation.py',
           ROOT/'tests/haptics_driver_emulation.py',ROOT/'scripts/firmware_facts.py',
           ROOT/'tests/haptics-emulator-dependencies.json',ROOT/'scripts/audit_haptics_devicetree.py']
    report=dict(status='PASS',scope=__doc__.strip(),cases=cases,drivers=drivers,
                sources={str(dtpath.relative_to(ROOT)):sha(dtpath),**dt['sources']},
                tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
                libfdt_sources=dt['libfdt_sources'],
                emulator_files={str(p.relative_to(ROOT)):sha(p) for p in sorted(DEPS.rglob('*'))
                                if p.is_file() and p.suffix in ('.py','.so')})
    (ROOT/'logs/haptics-probe-emulation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':main()
