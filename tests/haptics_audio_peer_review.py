#!/usr/bin/env python3
"""Execute the original OS4 audio peer for the captured vibrator startup packet.

Original socket handler, ResourceManager notification, MiModulePrimary stream
traversal and updateA2HMode execute. Singleton initialization is supplied as
complete. Socket I/O, mutexes, weak-reference acquisition, stream/usecase and app
policy, setA2HParameter and logging are fixtures. Atomic release runs serially;
there is no live Android service, real audio stream, ALSA, DSP or motor.
Unknown calls or execution outside the reviewed functions fail closed.
"""
import io
import json
import re
import struct
import subprocess
from pathlib import Path

from haptics_driver_emulation import ROOT, DEPS, sha, MASK
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X30,
                                UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_TPIDR_EL0)

LLVM = Path('/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin')
PREFIX = '_ZN4aidl7android8hardware5audio4core'
HANDLER = '_ZN23VibratorHalSocketServer24audio_handle_client_sockEjiP17audio_agm_ext_con'
MANAGER = PREFIX + '15ResourceManager28noteHapticStreamStatusChangeEb'
MODULE = PREFIX + '15MiModulePrimary28noteHapticStreamStatusChangeEb'
A2H = PREFIX + '18MiStreamOutPrimary13updateA2HModeEb'
ATOMIC = '_ZN7android17AudioResamplerDynIisiE8InBuffer10setImpulseEPs'
OBJ, STACK, RETURN = 0x4000000, 0x5000000, 0x6000000
HASHES = {'os4-current': 'b6387068491553e46600984c889cac1f4fc76ba4f6de1fd8125b164e183d18f8',
          'os4-stable': 'eec232a6a96a6b38cca3834e740047be33adc05fc9019087826da5aaeb4a261b'}


class Peer:
    def __init__(self, path, disasm, relocations, scenario, packet):
        self.u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        elf = ELFFile(io.BytesIO(path.read_bytes()))
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                start = segment['p_vaddr'] & ~4095
                length = (segment['p_vaddr'] - start + segment['p_memsz'] + 4095) & ~4095
                self.u.mem_map(start, length)
                self.u.mem_write(segment['p_vaddr'], segment.data())
        self.symbols = {s.name: (s['st_value'], s['st_size'])
                        for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_value']}
        self.ranges = [self.symbols[n] for n in [HANDLER, MANAGER, MODULE, A2H]]
        # Disassembly independently identifies this internal atomic release
        # entry at the exported thunk+8; execute both LSE/fallback original code.
        atomic = self.symbols[ATOMIC][0] + 8
        assert re.search(r'bl\s+0x' + format(atomic, 'x') + r'\s+<[^>]+setImpulseEPs\+0x8>', disasm)
        self.ranges.append((atomic, 48))
        self.plt = {int(a, 16): n for a, n in re.findall(
            r'^([0-9a-f]+) <([^>]+)@plt>:', disasm, re.M)}
        for base, length in [(OBJ, 0x20000), (STACK, 0x20000), (RETURN, 4096)]:
            self.u.mem_map(base, length)
        # Resolve only reviewed GOT entries; fail if a new original dependency
        # is reached instead of silently providing a generic successful call.
        bindings = {
            'gXAudioLogLevel': OBJ + 0x1000,
            '_ZZN4aidl7android8hardware5audio4core15ResourceManager11GetInstanceEvE2rm': OBJ + 0x2000,
            '_ZGVZN4aidl7android8hardware5audio4core15ResourceManager11GetInstanceEvE2rm': OBJ + 0x3000,
            PREFIX + '15MiModulePrimary21is_support_cirrus_A2HE': OBJ + 0x4000,
            PREFIX + '13ModulePrimary12outListMutexE': OBJ + 0x5000,
            PREFIX + '13ModulePrimary11mStreamsOutE': OBJ + 0x6000,
            PREFIX + '15MiModulePrimary20is_media_haptic_modeE': OBJ + 0xf000,
            PREFIX + '18MiStreamOutPrimary10playingAppE': OBJ + 0x11000,
            PREFIX + '18MiStreamOutPrimary21a2hAllowStreamUsecaseE': OBJ + 0x12000,
            PREFIX + '18MiStreamOutPrimary20vibratorStreamStatusE': OBJ + 0x13000,
        }
        for symbol, value in bindings.items():
            matches = re.findall(r'^([0-9a-f]+)\s+\S+\s+R_AARCH64_GLOB_DAT\s+\S+\s+' +
                                 re.escape(symbol) + r' \+ 0$', relocations, re.M)
            assert len(matches) == 1, (symbol, matches)
            self.u.mem_write(int(matches[0], 16), struct.pack('<Q', value))
        self.u.mem_write(OBJ + 0x3000, b'\1')
        self.u.mem_write(OBJ + 0x4000, bytes([scenario != 'feature-disabled']))
        if scenario == 'expired-stream' or scenario.startswith('active-'):
            self.u.mem_write(OBJ + 0x6000, struct.pack('<QQQ', OBJ + 0x7000, OBJ + 0x7010, OBJ + 0x7010))
            self.u.mem_write(OBJ + 0x7000, struct.pack('<QQ', OBJ + 0x8000, OBJ + 0x9000))
        self.u.mem_write(OBJ + 0x9008, struct.pack('<Q', 2))
        self.u.mem_write(OBJ + 0xf000, b'\1')
        self.u.mem_write(OBJ + 0x12000, struct.pack('<QQQ', OBJ + 0x14000, OBJ + 0x14004, OBJ + 0x14004))
        self.u.mem_write(OBJ + 0x14000, struct.pack('<I', 7))
        self.u.reg_write(UC_ARM64_REG_TPIDR_EL0, OBJ + 0xa000)
        self.scenario, self.packet = scenario, packet
        self.calls, self.entries = [], []
        self.u.hook_add(UC_HOOK_CODE, self.hook)

    def arg(self, i):
        return self.u.reg_read(UC_ARM64_REG_X0 + i)

    def hook(self, u, address, size, data):
        for name in [HANDLER, MANAGER, MODULE, A2H]:
            if address == self.symbols[name][0]:
                self.entries.append(dict(function=name, args=[self.arg(i) for i in range(4)]))
        if address not in self.plt:
            assert any(start <= address < start + length for start, length in self.ranges), hex(address)
            return
        name = self.plt[address]
        args = [self.arg(i) for i in range(4)]
        if name in [MANAGER, MODULE, A2H]:
            u.reg_write(UC_ARM64_REG_PC, self.symbols[name][0])
            return
        record = dict(call=name)
        if name == '__android_log_print':
            result = 0
        elif name == 'read':
            assert args[0] == 55 and args[2] == 72
            result = -1 if self.scenario == 'read-error' else len(self.packet)
            if result > 0:
                u.mem_write(args[1], self.packet)
            record.update(result=result, data=self.packet.hex())
        elif name == 'write':
            assert args[0] == 55 and args[2] == 2
            record['data'] = bytes(u.mem_read(args[1], 2)).hex()
            result = -1 if self.scenario == 'write-error' else 2
        elif name in ['_ZNSt3__15mutex4lockEv', '_ZNSt3__15mutex6unlockEv']:
            assert args[0] == OBJ + 0x5000
            result = 0
        elif name == '_ZNSt3__119__shared_weak_count4lockEv':
            assert args[0] == OBJ + 0x9000
            result = 0 if self.scenario == 'expired-stream' else OBJ + 0x9000
        elif name == PREFIX + '16StreamPrimaryOut10getUsecaseERKNSt3__16vectorINS0_5media5audio6common11AudioDeviceENS5_9allocatorISA_EEEE':
            assert args[0] == OBJ + 0x8000 and bytes(u.mem_read(args[1], 24)) == bytes(24)
            result = 8 if self.scenario == 'active-unmatched' else 7
        elif name == PREFIX + '18MiStreamOutPrimary24isStreamOfStatusAllowA2HEv':
            assert args[0] == OBJ + 0x8000
            result = 1
        elif name == PREFIX + '21isA2HAppNameListAllowENSt3__16vectorINS4_12basic_stringIcNS4_11char_traitsIcEENS4_9allocatorIcEEEENS9_ISB_EEEE':
            assert bytes(u.mem_read(args[0], 24)) == bytes(24)
            result = int(self.scenario != 'active-off-app-denied')
        elif name == PREFIX + '18MiStreamOutPrimary15setA2HParameterEPci':
            value = bytes(u.mem_read(args[0], 15))
            record.update(parameter=value.rstrip(b'\0').decode(), value=args[1])
            assert record['parameter'] == 'Haptics Source'
            result = 0
        elif name == '_ZN23VibratorHalSocketServer10del_clientEP17audio_agm_ext_coni':
            assert args[1:3] == [OBJ + 0xb000, 55]
            result = 0
        elif name == '__errno':
            self.u.mem_write(OBJ + 0xc000, struct.pack('<I', 5))
            result = OBJ + 0xc000
        elif name == 'strerror':
            assert args[0] == 5
            self.u.mem_write(OBJ + 0xd000, b'synthetic I/O error\0')
            result = OBJ + 0xd000
        else:
            raise AssertionError(('unreviewed external', name, args))
        record['result'] = result
        self.calls.append(record)
        u.reg_write(UC_ARM64_REG_X0, result & MASK)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))

    def run(self):
        events = 0x10 if self.scenario == 'hangup' else 0 if self.scenario == 'no-input' else 1
        for i, value in enumerate([OBJ, events, 55, OBJ + 0xb000]):
            self.u.reg_write(UC_ARM64_REG_X0 + i, value)
        self.u.reg_write(UC_ARM64_REG_SP, STACK + 0x1fff0)
        self.u.reg_write(UC_ARM64_REG_X30, RETURN)
        self.u.emu_start(self.symbols[HANDLER][0], RETURN, count=100000, timeout=2000000)
        assert self.u.reg_read(UC_ARM64_REG_PC) == RETURN, 'instruction/time budget exhausted'


def main():
    cases, sources = [], {}
    prior = ROOT / 'logs/haptics-service-tail-review.json'
    source_report = json.loads(prior.read_text())
    assert source_report['status'] == 'PASS'
    sources[str(prior.relative_to(ROOT))] = sha(prior)
    labels = ['startup', 'off', 'unknown-command', 'short-command', 'short-state',
              'read-eof', 'read-error', 'hangup', 'no-input', 'write-error',
              'feature-disabled', 'expired-stream', 'state-high-byte-only',
              'active-on', 'active-off', 'active-off-app-denied', 'active-unmatched']
    for sample, digest in HASHES.items():
        base = ROOT / 'firmware/samples' / sample / 'analysis/vendor'
        binary = base / 'lib64/libaudioserviceimpl.so'
        rc = base / 'etc/init/android.hardware.audio.service-aidl.rc'
        assert sha(binary) == digest
        assert 'socket vibrator_audio_socket_0 seqpacket 0666 system system' in rc.read_text()
        ds = ROOT / 'logs' / (sample + '-haptics-audio-peer.disasm')
        rel = ROOT / 'logs' / (sample + '-haptics-audio-peer-relocations.txt')
        core = subprocess.check_output([str(LLVM/'llvm-objdump'), '-d',
                                       '--disassemble-symbols=' + ','.join([HANDLER, MANAGER, MODULE, A2H, ATOMIC]), str(binary)])
        plt = subprocess.check_output([str(LLVM/'llvm-objdump'), '-d', '--section=.plt', str(binary)])
        ds.write_bytes(core + plt)
        rel.write_bytes(subprocess.check_output([str(LLVM/'llvm-readelf'), '-rW', str(binary)]))
        for p in [binary, rc, ds, rel]:
            sources[str(p.relative_to(ROOT))] = sha(p)
        original, = [c for c in source_report['cases'] if c['sample'] == sample and c['case'] == 'normal']
        packet = bytes.fromhex(original['peer_messages'][0])
        assert packet == struct.pack('<III', 42, 1, 1) + bytes(60)
        for label in labels:
            data = bytearray(packet)
            if label in ['off', 'state-high-byte-only', 'active-off', 'active-off-app-denied']:
                data[8:12] = struct.pack('<I', 0 if label == 'off' else 256)
            if label == 'unknown-command':
                data[:4] = struct.pack('<I', 43)
            if label == 'short-command': data = data[:4]
            if label == 'short-state': data = data[:9]
            if label in ['read-eof', 'read-error']: data = bytearray()
            m = Peer(binary, ds.read_text(), rel.read_text(), label, bytes(data))
            m.run()
            functions = [e['function'] for e in m.entries]
            notify = label not in ['unknown-command', 'read-eof', 'read-error', 'hangup', 'no-input']
            assert functions.count(MANAGER) == int(notify), (sample, label, functions)
            module = notify and label != 'feature-disabled'
            assert functions.count(MODULE) == int(module)
            if notify:
                wanted = int(label not in ['off', 'short-command', 'state-high-byte-only', 'active-off', 'active-off-app-denied'])
                entry, = [e for e in m.entries if e['function'] == MANAGER]
                assert entry['args'][:2] == [OBJ + 0x2000, wanted]
            acks = [c for c in m.calls if c['call'] == 'write']
            assert len(acks) == int(label not in ['hangup', 'no-input'])
            if acks: assert acks[0]['data'] == '0100'
            assert sum(c['call'].endswith('mutex4lockEv') for c in m.calls) == int(module)
            assert sum(c['call'].endswith('mutex6unlockEv') for c in m.calls) == int(module)
            update = label.startswith('active-') and label != 'active-unmatched'
            assert functions.count(A2H) == int(update)
            parameters = [c for c in m.calls if c['call'].endswith('setA2HParameterEPci')]
            assert [c['value'] for c in parameters] == ([2] if label == 'active-off' else [0] if label == 'active-off-app-denied' else [])
            if label.startswith('active-'):
                assert bytes(m.u.mem_read(OBJ + 0x9008, 8)) == struct.pack('<Q', 1)
            cases.append(dict(sample=sample, case=label, status='PASS', packet=bytes(data).hex(),
                              entries=m.entries, calls=m.calls,
                              stream_fixture='synthetic active stream' if label.startswith('active-') else
                              'expired weak stream' if label == 'expired-stream' else 'empty output list'))
    tests = [Path(__file__).resolve(), ROOT/'tests/haptics_driver_emulation.py',
             ROOT/'tests/haptics-emulator-dependencies.json', ROOT/'scripts/firmware_facts.py']
    report = dict(status='PASS', scope=__doc__, cases=cases, sources=sources,
                  tests={str(p.relative_to(ROOT)): sha(p) for p in tests},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in DEPS.rglob('*')
                                  if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name)})
    (ROOT/'logs/haptics-audio-peer-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'original audio peer cases; ACK is not hardware readiness')


if __name__ == '__main__': main()
