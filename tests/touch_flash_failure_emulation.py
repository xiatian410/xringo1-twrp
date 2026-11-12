#!/usr/bin/env python3
"""Execute original OS4 reflash failure handling over synthetic v2 transport.

Stock firmware/container/CRC, identify, boot info, block checks, erase/write
command construction and reset execute original ARM64. Responses and geometry
are synthetic; erased/programmed bytes never reach hardware. Inject timeout at
erase or first/second write; no complete programming success is claimed.
No physical device, kernel scheduling or controller flash state is modeled.
"""
import json
from pathlib import Path
import struct
import subprocess
from touch_firmware_emulation import Firmware, areas, IMAGE
from touch_v2_startup_emulation import identity, frames, appinfo, CONFIG
from touch_startup_emulation import CORE, CTX, FW, INPUT, LAYOUTS
from haptics_driver_emulation import ROOT, DEPS, sha


def exercise(path, properties, children, blob):
    info=areas(blob); results=[]
    labels=['erase-app','erase-boot','erase-reset-error','write-first','write-second',
            'config-only','config-only-write','zero-block','large-block','zero-page',
            'boot-info-error','mode-stays-app']
    for label in labels:
        m=Firmware(path,properties,children,blob)
        ident=bytearray(identity())
        struct.pack_into('<I',ident,18,struct.unpack_from('<I',info['APP_CONFIG']['payload'],14)[0])
        m.responses=frames(0x10,bytes(ident))+frames(1)
        assert m.run('syna_tcm_detect_device',CORE,0,1)==1 and not m.responses
        m.uc.mem_write(CORE+0x80,info['APP_CONFIG']['payload'][18:34])
        config=label.startswith('config-only')
        if config:
            last=info['APP_CONFIG']['payload'][33]
            m.uc.mem_write(CORE+0x8f,bytes([last^1]))
        boot=bytearray(32)
        boot[4]=0 if label=='zero-block' else 128 if label=='large-block' else 8
        struct.pack_into('<HH',boot,5,0 if label=='zero-page' else 64,256)
        m.responses=frames(1,identity())+frames(0x10,identity(1 if label=='mode-stays-app' else 11))
        invalid=label in ['zero-block','large-block','zero-page','boot-info-error','mode-stays-app']
        if label!='mode-stays-app':
            m.responses+=([-110] if label=='boot-info-error' else frames(1,boot))
        if not invalid:
            successes=2 if label=='write-second' else 1 if label in ['write-first','config-only-write'] else 0
            m.responses+=frames(1)*successes+[-110]
            m.responses+=([-110] if label=='erase-reset-error' else frames(0x10,identity(11 if label=='erase-boot' else 1)))
        rc=m.run('syna_tcm_do_fw_update',CORE,IMAGE,len(blob),0,int(not config))
        assert rc==-5 and not m.responses and m.u32(CORE+0x328)==0
        assert m.completions==[CORE+0x380] and not m.events and not m.inputs
        assert len(m.crcs)==3 and len(m.comparisons)==int(config)
        packets=[bytes.fromhex(w['packet']) for w in m.writes]
        commands=[p[0] for p in packets]
        prefix=[10,9,2,31]+([] if label=='mode-stays-app' else [16])
        if invalid:
            assert commands==prefix
        else:
            assert commands==prefix+[17]+[18]*successes+[4]
            name='APP_CONFIG' if config else 'APP_CODE'; area=info[name]
            page=area['address']//128; count=(area['length']+127)//128
            erase=next(p for p in packets if p[0]==17)
            assert erase[4:-2]==struct.pack('<HH',page,count)
            writes=[p for p in packets if p[0]==18]
            for index,p in enumerate(writes):
                offset=index*240
                assert int.from_bytes(p[4:6],'little')==(area['address']+offset)//16
                assert p[6:-2]==area['payload'][offset:offset+240]
        mode=bytes(m.uc.mem_read(CORE,2)).hex()
        assert mode==('020b' if label in ['erase-boot','erase-reset-error','zero-block','large-block','zero-page','boot-info-error'] else '0201')
        print(label,rc,commands,mode,flush=True)
        results.append(dict(case=label,status='PASS',result=rc,mode=mode,pending=m.u32(CORE+0x328),
            commands=commands,writes=m.writes,reads=m.reads,completions=m.completions,
            comparisons=m.comparisons,crcs=m.crcs,inputs=m.inputs,events=m.events,prints=m.prints))
    return results


def joined(path, properties, children, blob):
    results=[]
    build=struct.unpack_from('<I',areas(blob)['APP_CONFIG']['payload'],14)[0]
    for missing in [False,True]:
        for reset_mode in [1,11]:
            m=Firmware(path,properties,children,blob)
            def ident(mode):
                value=bytearray(identity(mode));struct.pack_into('<I',value,18,build+1)
                return bytes(value)
            m.responses=frames(0x10,ident(1))+frames(1)+frames(1,appinfo())
            m.responses+=([-110]+frames(0x10,ident(11)) if missing else frames(1,CONFIG)+frames(1)*2)
            assert m.run('syna_dev_connect',CTX)==0 and not m.responses
            assert m.u32(CORE+0x18c)==(0 if missing else 13)
            m.writes=[]; m.reads=[]
            boot=bytearray(32);boot[4]=8;struct.pack_into('<HH',boot,5,64,256)
            current_mode=11 if missing else 1
            for _ in range(3):
                m.responses+=frames(1,ident(current_mode))
                if current_mode==1:m.responses+=frames(0x10,ident(11))
                m.responses+=frames(1,boot)+[-110]+frames(0x10,ident(reset_mode))
                current_mode=reset_mode
            m.run('syna_dev_reflash_startup_work',CTX+0x3d0)
            assert not m.responses and len(m.update_calls)==3
            assert len(m.completions)==3 and m.u32(CORE+0x328)==0
            assert m.released==[FW] and len(m.inputs)==1 and m.u64(CTX+0x3b8)==INPUT
            commands=[bytes.fromhex(w['packet'])[0] for w in m.writes]
            assert commands.count(17)==commands.count(4)==commands.count(16)==3
            assert 18 not in commands and 32 not in commands and 37 not in commands
            mode=bytes(m.uc.mem_read(CORE,2)).hex()
            assert mode==('0201' if reset_mode==1 else '020b')
            m.report_frames()
            assert m.run('syna_dev_isr',0,CTX)==1 and not m.responses
            assert m.u32(CORE+0x18c)==(0 if missing else 13)
            if missing:assert not m.events
            else:assert [INPUT,3,53,64400] in m.events
            label=f'joined-{"missing" if missing else "existing"}-config-reset-{reset_mode}'
            print(label,'registered',len(m.inputs),'events',len(m.events),mode,flush=True)
            results.append(dict(case=label,status='PASS',result=None,mode=mode,
                config_length=m.u32(CORE+0x18c),commands=commands,updates=m.update_calls,
                writes=m.writes,reads=m.reads,completions=m.completions,pending=m.u32(CORE+0x328),
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
        disasm = ROOT/'logs'/f'{sample}-touch-flash-failure-core.disasm'
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-dr',
            '--disassemble-symbols=syna_tcm_do_fw_update,syna_tcm_set_up_flash_access,syna_tcm_do_reflash_generic,syna_tcm_update_flash_block,syna_tcm_check_flash_block,syna_tcm_erase_flash_block,syna_tcm_write_flash_block,syna_tcm_reset', str(path)]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
        properties = {k:bytes.fromhex(v) if isinstance(v,str) else v for k,v in record['canonical_touch_properties'].items()}
        children = {n:{k:bytes.fromhex(v) for k,v in p.items()} for n,p in record['touch_child_properties'].items()}
        results = exercise(path, properties, children, firmware.read_bytes())
        results+=joined(path, properties, children, firmware.read_bytes())
        assert len(results) == 16 and len({c['case'] for c in results}) == 16
        cases.extend(dict(sample=sample, **c) for c in results)
    tests = [Path(__file__).resolve()]+[ROOT/'tests'/n for n in [
        'touch_firmware_emulation.py', 'touch_v2_panel_startup_emulation.py', 'touch_v2_startup_emulation.py', 'touch_v2_command_emulation.py',
        'touch_message_emulation.py', 'touch_spi_emulation.py', 'touch_configuration_emulation.py',
        'touch_startup_emulation.py', 'haptics_driver_emulation.py', 'haptics-emulator-dependencies.json']]
    deps = sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-flash-failure-emulation.json').write_text(json.dumps(dict(status='PASS', scope=__doc__.strip(),
        cases=cases, drivers=drivers, sources=sources, tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}), indent=2)+'\n')


if __name__ == '__main__': main()
