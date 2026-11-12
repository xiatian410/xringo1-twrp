#!/usr/bin/env python3
"""Execute original OS4 probe/upload through boost and brownout configuration.

Original merged DT, stock DSP firmware/bins and algorithm rows are bound inputs.
Explicit synthetic registers, all-FF sequences, mailbox/debugfs and kernel
services inherit the documented probe fixture. Writes do not mutate hardware.
All paths end in injected read/write/wseq errors before runtime PM/input; no DSP
execution, successful full probe, IRQ delivery or motor output is claimed.
"""
import json
from pathlib import Path
import subprocess
from haptics_probe_upload_emulation import ProbeUpload, ROOT, DEPS, CTX, sha
from haptics_coefficients_emulation import table, bin_writes
from haptics_firmware_emulation import inventory

WATCH=['cs40l26_bst_ctl_config','cs40l26_clip_lvl_config','cs40l26_dbc_enable',
       'cs40l26_zero_cross_config','cs40l26_noise_gate_config','cs40l26_aux_noise_gate_config',
       'cs40l26_calib_dt_config','cs40l26_brwnout_prevention_init','cs40l26_dc_wd_config']


class PostBoost(ProbeUpload):
    def __init__(self,path,blobs,properties):
        self.property_destinations=[]
        super().__init__(path,blobs,properties)

    def on_code(self,uc,address,size,data):
        if self.hooks.get(address)=='device_property_read_u32_array' and self.arg(2):
            self.property_destinations.append(dict(property=self.string(self.arg(1)),
                destination=self.arg(2)-CTX))
        return super().on_code(uc,address,size,data)


def expected_brownout(properties, old_vp, old_vb):
    # Independent rational conversion (no disassembly multiply constants).
    # DT parser stores vbbr fields first; original brownout code consumes that
    # first slot for 0x6408, and the second vpbr slot for 0x6404. Preserve evidence.
    def fields(prefix, threshold, old):
        def val(s): return properties['cirrus,'+prefix+'-'+s][0]
        return ((old & 0xff000000) | threshold | ((val('max-att-db')&15)<<8) |
                ((val('atk-step')&15)<<12) | ((val('atk-rate')&7)<<16) |
                ((val('wait')&3)<<19) | ((val('rel-rate')&7)<<21))
    vp=((properties['cirrus,vbbr-thld-uv'][0]//55000)+1)&63
    vb=((properties['cirrus,vpbr-thld-uv'][0]//47000)+13)&31
    return {0x6408:fields('vbbr',vp,old_vp),0x6404:fields('vpbr',vb,old_vb)}


def exercise(path, blobs, properties):
    rows=table(blobs['cs40l26.wmfw'])[1]
    raw=inventory(blobs['cs40l26.wmfw'])['writes'][:]
    for name in ['cs40l26.bin','cs40l26-svc.bin','cs40l26-dvl.bin','cs40l26-a2h.bin','cs40l26-dbc.bin']:
        raw+=bin_writes(blobs[name],rows)
    results=[]
    scenarios=[('clip-read',0x7068,None,None),('clip-write',None,0x7068,None),
        ('brownout-enable-read',0x201c,None,None),('brownout-enable-write',None,0x201c,None),
        ('VPBR-read',0x6408,None,None),('VPBR-write',None,0x6408,None),
        ('VBBR-read',0x6404,None,None),('VBBR-write',None,0x6404,None),
        ('brownout-IRQ-read',0x10114,None,None),
        ('VPBR-high-sequence',None,None,19),('VPBR-low-sequence',None,None,20),
        ('VBBR-high-sequence',None,None,21),('VBBR-low-sequence',None,None,22)]
    for label,read,write,bulk in scenarios:
        m=PostBoost(path,blobs,properties)
        m.watch+=WATCH
        m.hardware.update({0x381c:0xffffffff,0x3804:0,0x7068:0,0x201c:0,
                           0x6408:0xa5000000,0x6404:0x5a000000})
        if read is not None:m.read_errors[read]=-5
        if write is not None:m.failed_write_address=write
        if bulk is not None:m.bulk_failure=bulk
        rc=m.run('cs40l26_probe',CTX)
        assert rc==-5,(label,rc)
        assert m.removed==[CTX] and 'cs40l26_input_init' not in m.entries
        assert 'cs40l26_dc_wd_config' not in m.entries
        assert bytes(m.uc.mem_read(CTX+0x1ca,1))==b'\1'
        assert m.raw==raw and len(m.raw)==68
        assert m.released==[m.fwmap[n] for n in m.requests]
        if read is not None:assert m.reads[-1]==dict(address=read,value=None,result=-5)
        if write is not None:assert any(w['address']==write for w in m.writes)
        if bulk is not None:assert len(m.bulk)==bulk and m.bulk[-1]['result']==-5
        expected=expected_brownout(properties,0xa5000000,0x5a000000)
        destinations={p['property']:p['destination'] for p in m.property_destinations}
        assert destinations['cirrus,vbbr-thld-uv']==0x1b74
        assert destinations['cirrus,vpbr-thld-uv']==0x1b90
        assert m.u32(CTX+0x1b74)==properties['cirrus,vbbr-thld-uv'][0]
        assert m.u32(CTX+0x1b90)==properties['cirrus,vpbr-thld-uv'][0]
        attempted={w['address']:w['value'] for w in m.writes if w['address'] in [0x201c,0x6408,0x6404]}
        for address,value in attempted.items():
            assert value==(0x3000 if address==0x201c else expected[address]),(label,hex(address),hex(value),expected)
        if label.startswith('VPBR-') or label.startswith('VBBR-') or label=='brownout-IRQ-read':
            assert 'cs40l26_brwnout_prevention_init' in m.entries
            assert attempted[0x201c]==0x3000
        if label=='brownout-IRQ-read':
            assert len(m.bulk)==22 and attempted=={0x201c:0x3000,**expected}
            assert all(n in m.entries for n in WATCH[:-1])
        print(label,rc,'raw',len(m.raw),'bulk',len(m.bulk),flush=True)
        results.append(dict(case=label,status='PASS',result=rc,fw_loaded=1,
            injected_read=read,injected_write=write,injected_bulk=bulk,
            entries=m.entries,remove_calls=m.removed,raw_writes=m.raw,
            register_reads=m.reads,writes=m.writes,bulk_writes=m.bulk,
            expected_brownout={hex(k):v for k,v in expected.items()},
            attempted_brownout={hex(k):v for k,v in attempted.items()},
            messages=m.messages,properties_read=m.property_reads))
        results[-1]['property_destinations']=m.property_destinations
    return results


def main():
    dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text())
    sources={str(dtpath.relative_to(ROOT)):sha(dtpath)};cases=[];drivers={}
    for field in ['sources','libfdt_sources']:
        for name,expected in dt[field].items():
            p=Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p)==expected;sources[str(p)]=expected
    for sample in ['os4-current','os4-stable']:
        base=ROOT/'firmware/samples'/sample/'analysis'
        path=base/'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        node=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']
        assert node['active']
        files=sorted((base/'odm/firmware').glob('cs40l26*'))
        sources.update({str(p.relative_to(ROOT)):sha(p) for p in files})
        blobs={p.name:p.read_bytes() for p in files}
        disasm=ROOT/'logs'/f'{sample}-haptics-postboost-core.disasm'
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump','-dr',
            '--disassemble-symbols='+','.join(WATCH+['cs40l26_probe','cs40l26_dsp_config']),str(path)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        cases.extend(dict(sample=sample,**c) for c in exercise(path,blobs,node['properties']))
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in ['haptics_probe_upload_emulation.py',
        'haptics_config_emulation.py','haptics_coefficients_emulation.py','haptics_upload_emulation.py',
        'haptics_firmware_emulation.py','haptics_driver_emulation.py','haptics-emulator-dependencies.json']]+[ROOT/'scripts/firmware_facts.py']
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/haptics-postboost-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':main()
