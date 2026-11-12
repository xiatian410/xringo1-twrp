#!/usr/bin/env python3
"""Execute complete stock OS4 programming command generation and post-reset paths.

Original ARM64 firmware parsing/CRC, block checks, erase/write/reset, v2 framing,
background app/config retrieval and ISR execute. Explicit synthetic transport
responses acknowledge writes without modeling controller flash contents. Full
byte/address inventories verify every requested programming chunk. No physical
flash, kernel workqueue/IRQ scheduling or successful hardware boot is claimed.
"""
import json
import hashlib
from pathlib import Path
import struct
import subprocess
from touch_firmware_emulation import Firmware, areas, IMAGE
from touch_v2_startup_emulation import identity, frames, appinfo, CONFIG
from touch_startup_emulation import CORE, CTX, FW, INPUT, LAYOUTS
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_PC, UC_ARM64_REG_SP


class Complete(Firmware):
    def on_code(self,uc,address,size,data):
        # Preserve original instructions and all service hooks, avoid fetching
        # seven argument registers at each irrelevant ARM64 instruction.
        if address not in self.hooks and address not in [self.symbols['syna_tcm_do_fw_update'],
                                                         self.symbols['syna_tcm_compare_image_id_info']]:
            return
        return super().on_code(uc,address,size,data)

    def run(self,name,*args):
        if name not in ['syna_tcm_do_fw_update','syna_dev_reflash_startup_work']:
            return super().run(name,*args)
        for i,value in enumerate(args):self.uc.reg_write(UC_ARM64_REG_X0+i,value&MASK)
        self.uc.reg_write(UC_ARM64_REG_SP,0x5020000-16)
        self.uc.reg_write(UC_ARM64_REG_X30,self.return_address)
        self.uc.emu_start(self.symbols[name],self.return_address,timeout=45000000,count=20000000)
        assert self.uc.reg_read(UC_ARM64_REG_PC)==self.return_address,('emulation budget',name)
        value=self.arg(0)&0xffffffff
        return value if value<(1<<31) else value-(1<<32)


def inventory(blob,config_only=False):
    info=areas(blob);result=[]
    for name in (['APP_CONFIG'] if config_only else ['APP_CODE','APP_CONFIG']):
        area=info[name]
        result.append(bytes([17])+struct.pack('<HH',area['address']//128,(area['length']+127)//128))
        for offset in range(0,area['length'],240):
            result.append(bytes([18])+struct.pack('<H',(area['address']+offset)//16)+area['payload'][offset:offset+240])
    return result


def ident(blob,mode=1,mismatch=False):
    value=bytearray(identity(mode))
    struct.pack_into('<I',value,18,struct.unpack_from('<I',areas(blob)['APP_CONFIG']['payload'],14)[0]+int(mismatch))
    return bytes(value)


def setup(blob,current=1):
    boot=bytearray(32);boot[4]=8;struct.pack_into('<HH',boot,5,64,256)
    return frames(1,ident(blob,current))+ (frames(0x10,ident(blob,11)) if current==1 else [])+frames(1,boot)


def check_packets(m,expected):
    packets=[bytes.fromhex(w['packet']) for w in m.writes]
    actual=[bytes([p[0]])+p[4:-2] for p in packets if p[0] in [17,18]]
    assert actual==expected
    return [dict(command=p[0],length=len(p)-1,sha256=hashlib.sha256(p[1:]).hexdigest()) for p in actual]


def exercise(path,properties,children,blob):
    results=[]
    labels=['full','config-only','reset-bootloader','reset-timeout','app-last-write-error',
            'config-erase-error','config-last-write-error','reset-rejects-status']
    for label in labels:
        m=Complete(path,properties,children,blob)
        m.responses=frames(0x10,ident(blob))+frames(1)
        assert m.run('syna_tcm_detect_device',CORE,0,1)==1 and not m.responses
        m.uc.mem_write(CORE+0x80,areas(blob)['APP_CONFIG']['payload'][18:34])
        config=label=='config-only'
        if config:
            value=areas(blob)['APP_CONFIG']['payload'][33]
            m.uc.mem_write(CORE+0x8f,bytes([value^1]))
        expected=inventory(blob,config)
        failure=None
        if label=='app-last-write-error':failure=next(i for i,p in enumerate(expected[1:],1) if p[0]==17)-1
        if label=='config-erase-error':failure=next(i for i,p in enumerate(expected[1:],1) if p[0]==17)
        if label=='config-last-write-error':failure=len(expected)-1
        limit=len(expected) if failure is None else failure+1
        m.responses=setup(blob)+frames(1)*(len(expected) if failure is None else failure)
        if failure is not None:m.responses += [-110]
        m.responses+=([-110] if label=='reset-timeout' else frames(4) if label=='reset-rejects-status' else
                       frames(0x10,ident(blob,11 if label=='reset-bootloader' else 1)))
        rc=m.run('syna_tcm_do_fw_update',CORE,IMAGE,len(blob),0,int(not config))
        print(label,rc,'remaining',len(m.responses),'writes',len(m.writes),flush=True)
        assert rc==(-5 if failure is not None or label in ['reset-timeout','reset-rejects-status'] else 0)
        assert not m.responses and m.u32(CORE+0x328)==0 and m.completions==[CORE+0x380]
        checked=check_packets(m,expected[:limit])
        mode=bytes(m.uc.mem_read(CORE,2)).hex()
        assert mode==('020b' if label in ['reset-bootloader','reset-timeout','reset-rejects-status'] else '0201')
        assert len(m.update_calls)==1 and len(m.crcs)==3 and len(m.comparisons)==int(config)
        results.append(dict(case=label,status='PASS',result=rc,mode=mode,pending=m.u32(CORE+0x328),
            checked_chunks=checked,programming_writes=sum(c['command']==18 for c in checked),
            erase_commands=sum(c['command']==17 for c in checked),completions=m.completions,
            commands=[bytes.fromhex(w['packet'])[0] for w in m.writes],prints=m.prints))
    return results


def joined(path,properties,children,blob):
    results=[]
    for label in ['joined-restored','joined-reset-bootloader','joined-config-timeout',
                  'joined-config-empty','joined-retry-after-config-last-error']:
        m=Complete(path,properties,children,blob)
        m.responses=frames(0x10,ident(blob,mismatch=True))+frames(1)+frames(1,appinfo())
        m.responses+=[-110]+frames(0x10,ident(blob,11,mismatch=True))
        assert m.run('syna_dev_connect',CTX)==0 and not m.responses
        assert m.u32(CORE+0x18c)==0 and not m.inputs
        m.writes=[];m.reads=[]
        expected=inventory(blob)
        if label=='joined-retry-after-config-last-error':
            m.responses+=setup(blob,11)+frames(1)*(len(expected)-1)+[-110]+frames(0x10,ident(blob,mismatch=True))
        reset_mode=11 if label=='joined-reset-bootloader' else 1
        m.responses+=setup(blob,11 if label!='joined-retry-after-config-last-error' else 1)
        m.responses+=frames(1)*len(expected)+frames(0x10,ident(blob,reset_mode))
        if label!='joined-reset-bootloader':
            m.responses+=frames(1,appinfo())
            if label=='joined-config-timeout':m.responses+=[-110]
            else:m.responses+=frames(1,b'' if label=='joined-config-empty' else CONFIG)
        m.run('syna_dev_reflash_startup_work',CTX+0x3d0)
        print(label,'remaining',len(m.responses),'input',len(m.inputs),'config',m.u32(CORE+0x18c),flush=True)
        assert not m.responses and m.released==[FW] and len(m.inputs)==1
        repeats=2 if label=='joined-retry-after-config-last-error' else 1
        assert len(m.update_calls)==len(m.completions)==repeats and m.u32(CORE+0x328)==0
        checked=check_packets(m,expected*repeats)
        commands=[bytes.fromhex(w['packet'])[0] for w in m.writes]
        assert commands.count(32)==commands.count(37)==int(label!='joined-reset-bootloader')
        m.report_frames()
        assert m.run('syna_dev_isr',0,CTX)==1 and not m.responses
        missing=label in ['joined-config-timeout','joined-config-empty','joined-reset-bootloader']
        assert m.u32(CORE+0x18c)==(0 if missing else 13)
        if missing:assert not m.events
        else:assert [INPUT,3,53,64400] in m.events
        mode=bytes(m.uc.mem_read(CORE,2)).hex()
        assert mode==('020b' if label=='joined-reset-bootloader' else '0201')
        results.append(dict(case=label,status='PASS',result=None,mode=mode,config_length=m.u32(CORE+0x18c),
            checked_chunks=checked,programming_writes=sum(c['command']==18 for c in checked),
            erase_commands=sum(c['command']==17 for c in checked),commands=commands,
            updates=m.update_calls,completions=m.completions,pending=m.u32(CORE+0x328),
            inputs=m.inputs,events=m.events,released=m.released,prints=m.prints))
    return results


def main():
    dtpath = ROOT/'logs/touch-devicetree-audit.json'; dt = json.loads(dtpath.read_text())
    sources = {str(dtpath.relative_to(ROOT)):sha(dtpath)}; drivers = {}; cases = []
    for field in ['sources', 'tests', 'libfdt_sources']:
        for name, expected in dt[field].items():
            p = Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p) == expected; sources[str(p)] = expected
    for record in dt['cases']:
        sample = record['sample']; base = ROOT/'firmware/samples'/sample/'analysis'
        path = base/'vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        firmware = base/'odm/firmware/synaptics_spi_dijun.img'
        assert sha(path) in LAYOUTS
        assert sha(firmware) == record['firmware']['/lib/firmware/synaptics_spi_dijun.img']
        sources[str(firmware.relative_to(ROOT))] = sha(firmware)
        drivers[sample] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
        disasm = ROOT/'logs'/f'{sample}-touch-flash-complete-core.disasm'
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-dr',
            '--disassemble-symbols=syna_tcm_do_fw_update,syna_tcm_set_up_flash_access,syna_tcm_do_reflash_generic,syna_tcm_update_flash_block,syna_tcm_check_flash_block,syna_tcm_erase_flash_block,syna_tcm_write_flash_block,syna_tcm_reset,syna_dev_set_up_app_fw,syna_dev_reflash_startup,syna_dev_reflash_startup_work', str(path)]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
        properties = {k:bytes.fromhex(v) if isinstance(v,str) else v for k,v in record['canonical_touch_properties'].items()}
        children = {n:{k:bytes.fromhex(v) for k,v in p.items()} for n,p in record['touch_child_properties'].items()}
        results = exercise(path, properties, children, firmware.read_bytes())
        results+=joined(path, properties, children, firmware.read_bytes())
        assert len(results) == 13 and len({c['case'] for c in results}) == 13
        cases.extend(dict(sample=sample, **c) for c in results)
    tests = [Path(__file__).resolve()]+[ROOT/'tests'/n for n in [
        'touch_firmware_emulation.py', 'touch_v2_panel_startup_emulation.py', 'touch_v2_startup_emulation.py', 'touch_v2_command_emulation.py',
        'touch_message_emulation.py', 'touch_spi_emulation.py', 'touch_configuration_emulation.py',
        'touch_startup_emulation.py', 'haptics_driver_emulation.py', 'haptics-emulator-dependencies.json']]
    deps = sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-flash-complete-emulation.json').write_text(json.dumps(dict(status='PASS', scope=__doc__.strip(),
        cases=cases, drivers=drivers, sources=sources, tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}), indent=2)+'\n')


if __name__ == '__main__': main()
