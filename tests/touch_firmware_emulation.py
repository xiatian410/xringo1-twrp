#!/usr/bin/env python3
"""Execute original OS4 firmware container parsing/comparison and joined startup.

Uses exact stock firmware bytes and ARM64 instructions; kernel crc32_le is an
independent zlib-backed service fixture. Controller identity/app/config/frame
responses are synthetic. Flash programming is not executed: differing/forced
images stop at original flash-access identify timeout. Power, panel/input/IRQ
registration, firmware delivery and kernel scheduling are explicit fixtures.
Background runs sequentially. No physical phone, SPI or firmware write is used.
"""
import json
from pathlib import Path
import struct
import subprocess
import zlib

from touch_v2_panel_startup_emulation import PanelStartup
from touch_v2_startup_emulation import identity, appinfo, frames, CONFIG
from touch_startup_emulation import CORE, CTX, FW, INPUT, LAYOUTS
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

IMAGE = 0x4300000


def areas(blob):
    assert struct.unpack_from('<I', blob)[0] == 0x4818472b
    count = struct.unpack_from('<I', blob, 4)[0]
    result = {}
    for off in struct.unpack_from('<'+'I'*count, blob, 8):
        assert off+4 <= len(blob)
        if struct.unpack_from('<I', blob, off)[0] != 0x7c05e516:
            continue  # Original parser also ignores non-area table entries.
        name = blob[off+4:off+20].rstrip(b' \0').decode()
        address, length, crc = struct.unpack_from('<III', blob, off+24)
        payload = blob[off+36:off+36+length]
        assert len(payload) == length and zlib.crc32(payload) == crc
        result[name] = dict(offset=off, address=address*2, length=length, crc=crc, payload=payload)
    assert set(result) == {'BOOT_CONFIG', 'APP_CODE', 'APP_CONFIG'}
    return result


class Firmware(PanelStartup):
    def __init__(self, path, properties, children, blob):
        super().__init__(path, properties, children)
        del self.hooks[self.symbols['syna_tcm_do_fw_update']]
        self.uc.mem_map(IMAGE, 0x40000)
        self.uc.mem_write(IMAGE, blob)
        self.blob = blob
        self.put64(FW, len(blob)); self.put64(FW+8, IMAGE)
        self.crcs = []; self.comparisons = []; self.update_calls = []; self.completions = []

    def on_code(self, uc, address, size, data):
        if address == self.symbols['syna_tcm_do_fw_update']:
            self.update_calls.append([self.arg(i) for i in range(5)])
        if address == self.symbols['syna_tcm_compare_image_id_info']:
            context = self.arg(1)
            records = []
            for i in range(20):
                p = context+0x10+i*32
                if bytes(uc.mem_read(p, 1)) == b'\1':
                    records.append(dict(index=i, data=self.u64(p+8), length=self.u32(p+16),
                                        address=self.u32(p+20), area_index=self.u32(p+24)&255))
            self.comparisons.append(records)
        name = self.hooks.get(address)
        args = [self.arg(i) for i in range(7)]
        if name == 'crc32_le':
            assert IMAGE <= args[1] < IMAGE+len(self.blob)
            assert 0 <= args[2] <= len(self.blob) and args[1]+args[2] <= IMAGE+len(self.blob)
            raw = bytes(uc.mem_read(args[1], args[2]))
            result = zlib.crc32(raw, (args[0]&0xffffffff)^0xffffffff)^0xffffffff
            self.crcs.append(dict(offset=args[1]-IMAGE, length=args[2], seed=args[0]&0xffffffff, result=result))
        elif name == 'strncmp':
            assert args[2] <= 16
            a = bytes(uc.mem_read(args[0], args[2])).split(b'\0')[0]
            b = bytes(uc.mem_read(args[1], args[2])).split(b'\0')[0]
            result = (a > b)-(a < b)
        elif name == 'complete_all':
            self.completions.append(args[0]); result = 0
        else:
            return super().on_code(uc, address, size, data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))


def exercise(path, properties, children, original):
    info = areas(original); app = info['APP_CONFIG']['payload']
    build = struct.unpack_from('<I', app, 14)[0]; version = app[18:34]
    assert len(version) == 16
    results = []
    labels = ['match', 'build-mismatch', 'config-mismatch', 'config-last-mismatch', 'forced', 'bad-magic',
              'bad-BOOT_CONFIG-crc', 'bad-APP_CODE-crc', 'bad-APP_CONFIG-crc',
              'joined-match', 'joined-match-config-restored', 'joined-bad-crc', 'joined-missing-config-flash-access-fails']
    for label in labels:
        blob = bytearray(original)
        if label == 'bad-magic': blob[0] ^= 1
        if label.startswith('bad-') and label.endswith('-crc'):
            blob[info[label[4:-4]]['offset']+36] ^= 1
        if label == 'joined-bad-crc': blob[info['APP_CONFIG']['offset']+36] ^= 1
        m = Firmware(path, properties, children, bytes(blob))
        ident = bytearray(identity()); struct.pack_into('<I', ident, 18, build)
        app_response = bytearray(appinfo()); app_response[16:32] = version
        joined = label.startswith('joined-')
        if joined:
            m.responses = frames(0x10, bytes(ident))+frames(1)+frames(1, bytes(app_response))
            if label in ['joined-match-config-restored', 'joined-missing-config-flash-access-fails']:
                m.responses += [-110]+frames(0x10, identity(11))
            else:
                m.responses += frames(1, CONFIG)+frames(1)*2
            assert m.run('syna_dev_connect', CTX) == 0 and not m.responses
            if label == 'joined-match-config-restored':
                m.responses = frames(0x10, bytes(ident))
                assert m.run('syna_tcm_switch_fw_mode', CORE, 1, 200) == 0
                assert not m.responses and m.u32(CORE+0x18c) == 0
            m.request_error = 0
            m.responses = ([-110]*3 if label.endswith('flash-access-fails') else
                           frames(1, bytes(app_response))+frames(1, CONFIG) if label.startswith('joined-match') else [])
            # Work callback is void. Record no leftover return register as a
            # success code; assert original side effects below instead.
            m.run('syna_dev_reflash_startup_work', CTX+0x3d0)
            rc = None
            m.report_frames()
            assert m.run('syna_dev_isr', 0, CTX) == 1 and not m.responses
        else:
            m.responses = frames(0x10, bytes(ident))+frames(1)
            assert m.run('syna_tcm_detect_device', CORE, 0, 1) == 1 and not m.responses
            m.writes = []; m.reads = []
            m.put32(CORE+4, build+(label == 'build-mismatch'))
            m.uc.mem_write(CORE+0x80, version)
            if label == 'config-mismatch': m.uc.mem_write(CORE+0x80, bytes([version[0]^1]))
            if label == 'config-last-mismatch': m.uc.mem_write(CORE+0x8f, bytes([version[-1]^1]))
            m.responses = [-110] if label in ['build-mismatch', 'config-mismatch', 'config-last-mismatch', 'forced'] else []
            rc = m.run('syna_tcm_do_fw_update', CORE, IMAGE, len(blob), 0, int(label == 'forced'))
        malformed = label.startswith('bad-') or label == 'joined-bad-crc'
        expected_updates = 3 if label in ['joined-bad-crc', 'joined-missing-config-flash-access-fails'] else 1
        expected_crcs = (0 if label == 'bad-magic' else
                         2 if label == 'bad-BOOT_CONFIG-crc' else
                         3 if label == 'bad-APP_CODE-crc' else
                         4 if label in ['bad-APP_CONFIG-crc', 'joined-bad-crc'] else 3)*expected_updates
        assert len(m.update_calls) == expected_updates and len(m.crcs) == expected_crcs
        assert m.u32(CORE+0x328) == 0 and not m.responses
        assert m.completions == ([] if malformed else [CORE+0x380]*expected_updates)
        parsed = not malformed and label not in ['forced', 'joined-missing-config-flash-access-fails']
        assert len(m.comparisons) == int(parsed)
        if parsed:
            assert m.comparisons == [[dict(index=index, data=IMAGE+info[name]['offset']+36,
                length=info[name]['length'], address=info[name]['address'], area_index=index)
                for index, name in [(2, 'BOOT_CONFIG'), (3, 'APP_CODE'), (5, 'APP_CONFIG')]]]
        commands = [int(w['packet'][:2], 16) for w in m.writes]
        if joined:
            assert rc is None and len(m.inputs) == 1 and m.u64(CTX+0x3b8) == INPUT
            assert m.released == [FW] and m.requests == ['synaptics_spi_dijun.img']
            missing = label == 'joined-missing-config-flash-access-fails'
            assert m.u32(CORE+0x18c) == (0 if missing else 13)
            assert bytes(m.uc.mem_read(CORE, 2)).hex() == ('020b' if missing else '0201')
            if missing:
                assert not m.events and commands == [10, 9, 32, 37, 31, 2, 2, 2, 10]
            else:
                assert [INPUT, 3, 53, 64400] in m.events and [INPUT, 3, 54, 158900] in m.events
                expected_commands = ([10, 9, 32, 37, 31, 20] if label.endswith('config-restored') else
                                     [10, 9, 32, 37, 6, 5])
                assert commands == expected_commands+([32, 37] if label.startswith('joined-match') else [])+[10]
        else:
            assert not m.inputs and not m.events and not m.released
            assert rc == (-241 if malformed else 0 if label == 'match' else -5)
            assert commands == ([] if malformed or label == 'match' else [2])
        # All three valid stock areas passed crc32_le on unchanged firmware.
        if not malformed:
            assert [c['length'] for c in m.crcs] == [8, 143840, 5810]*expected_updates
            assert all(c['seed'] == 0xffffffff for c in m.crcs)
            expected_area_crcs = [info[n]['crc']^0xffffffff for n in ['BOOT_CONFIG', 'APP_CODE', 'APP_CONFIG']]
            assert [c['result'] for c in m.crcs] == expected_area_crcs*expected_updates
        print(label, rc, 'crc', len(m.crcs), 'updates', len(m.update_calls), 'events', len(m.events), flush=True)
        results.append(dict(case=label, status='PASS', result=rc, crcs=m.crcs,
            comparisons=m.comparisons, updates=m.update_calls, completions=m.completions,
            writes=m.writes, reads=m.reads, inputs=m.inputs, events=m.events,
            config_length=m.u32(CORE+0x18c), mode=bytes(m.uc.mem_read(CORE, 2)).hex(),
            pending=m.u32(CORE+0x328), released=m.released, remaining=len(m.responses), prints=m.prints))
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
        disasm = ROOT/'logs'/f'{sample}-touch-firmware-core.disasm'
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-dr',
            '--disassemble-symbols=syna_tcm_do_fw_update,syna_tcm_compare_image_id_info,syna_dev_reflash_startup', str(path)]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
        properties = {k:bytes.fromhex(v) if isinstance(v,str) else v for k,v in record['canonical_touch_properties'].items()}
        children = {n:{k:bytes.fromhex(v) for k,v in p.items()} for n,p in record['touch_child_properties'].items()}
        results = exercise(path, properties, children, firmware.read_bytes())
        assert len(results) == 13 and len({c['case'] for c in results}) == 13
        cases.extend(dict(sample=sample, **c) for c in results)
    tests = [Path(__file__).resolve()]+[ROOT/'tests'/n for n in [
        'touch_v2_panel_startup_emulation.py', 'touch_v2_startup_emulation.py', 'touch_v2_command_emulation.py',
        'touch_message_emulation.py', 'touch_spi_emulation.py', 'touch_configuration_emulation.py',
        'touch_startup_emulation.py', 'haptics_driver_emulation.py', 'haptics-emulator-dependencies.json']]
    deps = sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-firmware-emulation.json').write_text(json.dumps(dict(status='PASS', scope=__doc__.strip(),
        cases=cases, drivers=drivers, sources=sources, tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}), indent=2)+'\n')


if __name__ == '__main__': main()
