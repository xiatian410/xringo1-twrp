#!/usr/bin/env python3
"""Execute original OS4 selector/PCM and wave-data construction up to thread setup.

Discovery runs first in the same address space. The alternate-device/config-map
range 0x13084..0x1324c is skipped explicitly. Original library-vector setup is
executed separately, then selector/PCM/data construction is continuous through
0x1349c. AAC init executes in that context; AWA fallback is a recorded boundary.
Files, properties, mixer, libc/math and dynamic-loader/thread calls are fixtures.
Calibration restore remains a recorded boundary. No complete outer constructor,
plugin worker, thread, XML, ALSA, DSP or motor executes.
Ordinary on is then invoked in that partial context with XML long-id and the
restore-complete flag explicitly supplied, and a null callback (no timer).
"""
import json
import io
import math
import re
import struct
from pathlib import Path
import xml.etree.ElementTree as ET

from haptics_service_init_review import Startup, SYS
from haptics_service_route_review import Service, OBJ, RETURN
from haptics_driver_emulation import ROOT, DEPS, sha
from elftools.elf.elffile import ELFFile
from unicorn.arm64_const import UC_ARM64_REG_X19, UC_ARM64_REG_X22, UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_D0

AAC = 0x1000000
HEAP = 0x1200000
AAC_SHA = '3f8bb19b8a739fcd37ca557c83b808a48417bc7a1a10be95c7306530b62e1221'


class PCM(Startup):
    def __init__(self, path, disasm, label, props, plugin, plugin_disasm):
        super().__init__(path, disasm, 'normal')
        self.label, self.props = label, props
        self.libs, self.symbols, self.inits = [], [], []
        self.plugin_return = None
        self.frequency = {'f0-low-edge': 1200, 'f0-high-edge': 1400,
                          'f0-too-low': 1190, 'f0-too-high': 1410}.get(label, 1300)
        self.phase = 'discovery'
        assert sha(plugin) == AAC_SHA
        elf = ELFFile(io.BytesIO(plugin.read_bytes()))
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                start = segment['p_vaddr'] & ~4095
                length = (segment['p_vaddr'] - start + segment['p_memsz'] + 4095) & ~4095
                self.u.mem_map(AAC + start, length)
                self.u.mem_write(AAC + segment['p_vaddr'], segment.data())
        for relocation in elf.get_section_by_name('.rela.dyn').iter_relocations():
            assert relocation['r_info_type'] == 1027
            self.put64(AAC + relocation['r_offset'], AAC + relocation['r_addend'])
        self.plugin_plt = {AAC + int(a, 16): n for a, n in re.findall(
            r'^([0-9a-f]+) <([^>]+)@plt>:', plugin_disasm, re.M)}
        assert set(self.plugin_plt.values()) == {
            '__cxa_finalize', 'exp', 'sincos', '__android_log_print', 'malloc', 'cos',
            'memset', 'sin', 'memcpy', 'sem_init', 'pthread_mutex_init', 'pthread_create',
            'pthread_detach', 'sem_post', 'pthread_mutex_lock', 'sem_destroy',
            'pthread_mutex_unlock', 'sem_wait', 'printf', 'free', 'pow', '__stack_chk_fail'}
        self.u.mem_map(HEAP, 0x100000)
        self.plugin_heap, self.plugin_calls = HEAP, []

    def plugin_hook(self, name):
        u = self.u
        a = [self.arg(i) for i in range(4)]
        record = dict(call=name)
        if name == '__android_log_print':
            record['format'] = self.text(a[2])
            result = 0
        elif name == 'malloc':
            assert 0 < a[0] < 0x10000
            result = self.plugin_heap
            self.plugin_heap += (a[0] + 15) & ~15
            assert self.plugin_heap < HEAP + 0x100000
            record['size'] = a[0]
            if self.label == 'aac-allocation-error':
                assert not any(c['call'] == 'malloc' for c in self.plugin_calls)
                result = 0
        elif name == 'memset':
            assert HEAP <= a[0] and a[0] + a[2] <= self.plugin_heap
            u.mem_write(a[0], bytes([a[1] & 255]) * a[2])
            result = a[0]
        elif name == 'memcpy':
            assert HEAP <= a[0] and a[0] + a[2] <= self.plugin_heap
            u.mem_write(a[0], bytes(u.mem_read(a[1], a[2])))
            result = a[0]
        elif name in ['exp', 'cos', 'sin']:
            value = struct.unpack('<d', struct.pack('<Q', u.reg_read(UC_ARM64_REG_D0)))[0]
            computed = getattr(math, name)(value)
            u.reg_write(UC_ARM64_REG_D0, struct.unpack('<Q', struct.pack('<d', computed))[0])
            record.update(value=value, value_out=computed)
            result = 0
        elif name == 'sincos':
            value = struct.unpack('<d', struct.pack('<Q', u.reg_read(UC_ARM64_REG_D0)))[0]
            for pointer, computed in zip(a[:2], [math.sin(value), math.cos(value)]):
                u.mem_write(pointer, struct.pack('<d', computed))
            record['value'] = value
            result = 0
        elif name == 'sem_init':
            assert a[0] in [AAC + 0x1e978, AAC + 0x1e988] and a[1:3] == [0, 0], (name, a)
            record.update(address=a[0], value=a[2])
            result = -1 if self.label == 'aac-semaphore-error' else 0
        elif name == 'pthread_mutex_init':
            assert a[:2] == [AAC + 0x1e998, 0]
            result = 0
        elif name == 'pthread_create':
            assert a == [AAC + 0x1e9c0, 0, AAC + 0xf558, 0]
            record.update(entry=a[2], argument=a[3], executed=False)
            if self.label != 'aac-thread-error':
                self.put64(a[0], 123)
            result = 11 if self.label == 'aac-thread-error' else 0
        elif name == 'pthread_detach':
            assert a[0] == (0 if self.label == 'aac-thread-error' else 123)
            record['thread'] = a[0]
            result = 3 if self.label == 'aac-thread-error' else 0
        else:
            raise AssertionError(('unreviewed AAC init boundary', name, a))
        record['result'] = result
        self.plugin_calls.append(record)
        self.reply(result)

    def hook(self, u, address, size, data):
        if address == AAC + 0xea44:
            assert self.symbols[0]['name'] == 'aac_haptics_init'
            values = list(struct.unpack('<IIII', bytes(u.mem_read(self.arg(0), 16))))
            self.inits.append(dict(plugin='aac', values=values))
            return
        if address == 0x2961c:
            self.plugin_return = struct.unpack('<i', struct.pack('<I', self.arg(0) & 0xffffffff))[0]
            return
        if address in self.plugin_plt:
            return self.plugin_hook(self.plugin_plt[address])
        if self.phase == 'ordinary-on' and address in self.plt:
            return Service.hook(self, u, address, size, data)
        if address == RETURN + 0x200:
            self.inits.append(dict(plugin='awa', frequency=self.arg(0)))
            self.reply(0)
            return
        if address not in self.plt:
            return super().hook(u, address, size, data)
        name = self.plt[address]
        a = [self.arg(i) for i in range(8)]
        record = dict(call=name, phase=self.phase)
        if name == 'property_get':
            key = self.text(a[0])
            value = self.props['ro.product.odm.device'] if key == 'ro.product.device' else self.props.get(key)
            assert value is not None, ('unknown property', key)
            record.update(key=key, value=value)
            u.mem_write(a[1], value.encode() + b'\0')
            result = len(value)
        elif name == 'mixer_open' and self.phase == 'pcm':
            assert a[0] == 0
            result = 0 if self.label == 'mixer-absent' else OBJ + 0x9000
        elif name == 'access':
            assert self.text(a[0]) == SYS and a[1] == 0
            result = 0
            record['path'] = SYS
        elif name == '__vsnprintf_chk':
            # Android fortify formatter used by the original sysfs helper.
            assert self.text(a[4]) == '%s'
            va = a[5]
            gr_top = self.u64(va + 8)
            gr_off = struct.unpack('<i', bytes(u.mem_read(va + 24, 4)))[0]
            value = self.text(self.u64(gr_top + gr_off))
            assert value == SYS
            u.mem_write(a[0], value.encode() + b'\0')
            result = len(value)
        elif name == 'vsnprintf':
            assert self.text(a[2]) == '%s/%s' and a[1] == 256
            va = a[3]
            gr_top = self.u64(va + 8)
            gr_off = struct.unpack('<i', bytes(u.mem_read(va + 24, 4)))[0]
            values = [self.text(self.u64(gr_top + gr_off + i * 8)) for i in range(2)]
            assert values == [SYS, 'f0_value']
            value = '/'.join(values)
            u.mem_write(a[0], value.encode() + b'\0')
            record['formatted'] = value
            result = len(value)
        elif name == 'fopen':
            record.update(path=self.text(a[0]), mode=self.text(a[1]))
            assert record['path'] == SYS + '/f0_value' and record['mode'] == 'r'
            result = 0 if self.label == 'f0-absent' else OBJ + 0xb000
        elif name == 'fgets':
            assert a[1:3] == [256, OBJ + 0xb000]
            value = str(self.frequency) + '\n'
            u.mem_write(a[0], value.encode() + b'\0')
            record['value'] = value
            result = a[0]
        elif name == 'atoi':
            record['value'] = self.text(a[0])
            result = int(record['value'])
        elif name == 'dlopen':
            record.update(path=self.text(a[0]), flags=a[1])
            assert record['path'] in ['/odm/lib64/libaachaptics.so', '/odm/lib64/vendor.awa.wavelib.so'] and a[1] == 2, record
            result = 0 if self.label == 'all-libraries-absent' or (
                self.label == 'fallback-library' and not self.libs) else OBJ + 0xd000
            self.libs.append(dict(path=record['path'], result=result))
        elif name == 'dlsym':
            assert a[0] == OBJ + 0xd000
            symbol = self.text(a[1])
            assert symbol in ['aac_haptics_init', 'aac_haptics_process', 'aac_haptics_get_frame',
                              'awa_haptics_init', 'awa_haptics_get_waves_length', 'awa_haptics_get_waves_data']
            result = (RETURN + 0x200 if symbol.startswith('awa') else AAC + {
                'aac_haptics_init': 0xea44, 'aac_haptics_process': 0xf3a4, 'aac_haptics_get_frame': 0xf4ec}[symbol])
            if self.label == 'init-symbol-absent' and symbol == 'aac_haptics_init':
                result = 0
            self.symbols.append(dict(name=symbol, result=result))
            record['name'] = symbol
        else:
            return super().hook(u, address, size, data)
        record['result'] = result
        self.calls.append(record)
        self.reply(result)

    def interval(self, start, stop):
        self.u.emu_start(start, stop, count=1000000, timeout=10000000)
        assert self.u.reg_read(UC_ARM64_REG_PC) == stop, ('budget exhausted', hex(start))

    def construct(self):
        discovery = self.prefix()
        assert discovery == dict(fd=9, cirrus=1, mixer=OBJ + 0x9000)
        self.phase = 'library-vector'
        self.u.reg_write(UC_ARM64_REG_SP, 0x501fff0)
        self.interval(0x27f08, 0x27f44)
        begin, end = self.u64(0x34848), self.u64(0x34850)
        assert end - begin == 16
        library_names = [self.text(self.u64(begin + i * 8)) for i in range(2)]
        self.phase = 'pcm'
        self.u.reg_write(UC_ARM64_REG_SP, 0x501fff0)
        self.u.reg_write(UC_ARM64_REG_X19, OBJ)
        self.interval(0x1324c, 0x1349c)
        backend, data = self.u64(OBJ + 0x70), self.u.reg_read(UC_ARM64_REG_X22)
        # x22 is the original constructor's saved wave-data object pointer.
        assert OBJ + 0x12000 <= backend < data < OBJ + 0x18000
        return dict(discovery=discovery, selector=int.from_bytes(self.u.mem_read(0x34030, 4), 'little'),
                    sample_rate=int.from_bytes(self.u.mem_read(0x34034, 4), 'little'),
                    library_index=int.from_bytes(self.u.mem_read(0x34038, 4), 'little'),
                    libraries=library_names, backend=backend, data=data,
                    backend_vptr=self.u64(backend), mixer=self.u64(backend + 0x160),
                    port=self.text(backend + 0xd1),
                    pcm_config=list(struct.unpack('<IIIIII', bytes(self.u.mem_read(backend + 0x138, 24)))))


def main():
    cases, sources = [], {}
    labels = ['normal', 'mixer-absent', 'f0-absent', 'f0-low-edge', 'f0-high-edge',
              'f0-too-low', 'f0-too-high', 'fallback-library', 'all-libraries-absent', 'init-symbol-absent',
              'aac-allocation-error', 'aac-semaphore-error', 'aac-thread-error']
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis/odm'
        path = base / 'bin/hw/vendor.xring.hardware.vibratorfeature.service'
        disasm = ROOT / 'logs' / (sample + '-vibrator-service.disasm')
        propfile = base / 'etc/build.prop'
        plugin = base / 'lib64/libaachaptics.so'
        plugin_disasm = ROOT / 'logs' / (sample + '-haptics-aac-init.disasm')
        xml = base / 'etc/waveform_conf.xml'
        long_id = int(ET.fromstring(xml.read_bytes()).findtext('long_vib_id/data'))
        assert long_id == 31
        props = dict(line.split('=', 1) for line in propfile.read_text().splitlines() if '=' in line and not line.startswith('#'))
        assert props['ro.odm.mm.vibrator.device_type'] == 'pcm'
        assert props['ro.odm.mm.vibrator.resonant_frequency'] == '130'
        for p in [path, disasm, propfile, plugin, plugin_disasm, xml]:
            sources[str(p.relative_to(ROOT))] = sha(p)
        for label in labels:
            m = PCM(path, disasm.read_text(), label, props, plugin, plugin_disasm.read_text())
            state = m.construct()
            assert state['selector'] == 1 and state['sample_rate'] == 48000
            assert state['backend_vptr'] == 0x30670
            assert state['port'] == 'XR_TDM7_RX'
            assert state['pcm_config'] == [48000, 0, 24, 0, 4, 0]
            assert bool(state['mixer']) == (label != 'mixer-absent')
            expected_index = 2 if label == 'all-libraries-absent' else int(label == 'fallback-library')
            assert state['library_index'] == expected_index
            frequency = {'f0-low-edge': 120, 'f0-high-edge': 140}.get(label, 130)
            expected_init = [] if label in ['all-libraries-absent', 'init-symbol-absent'] else (
                [dict(plugin='awa', frequency=130)] if label == 'fallback-library' else
                [dict(plugin='aac', values=[512, 48000, 1, frequency])])
            assert m.inits == expected_init, (sample, label, m.inits)
            workers = [c for c in m.plugin_calls if c['call'] == 'pthread_create']
            assert len(workers) == int(bool(expected_init) and label not in
                                       ['fallback-library', 'aac-allocation-error', 'aac-semaphore-error'])
            assert all(not c['executed'] for c in workers)
            expected_return = None if label in ['fallback-library', 'all-libraries-absent', 'init-symbol-absent'] else {
                'aac-allocation-error': -2, 'aac-semaphore-error': -1, 'aac-thread-error': 11}.get(label, 0)
            assert m.plugin_return == expected_return, (sample, label, m.plugin_return)
            assert not any(c['call'] in ['write', 'ioctl', 'mixer_ctl_set_value', 'pcm_open'] for c in m.calls if c.get('phase') == 'pcm')
            boundary = len(m.calls)
            m.phase = 'ordinary-on'
            m.put32(0x3402c, long_id)  # XML parser not executed.
            m.u.mem_write(0x34308, b'\1')  # Restore-complete boundary, not its body.
            m.run(0x13e04, OBJ, 80, OBJ + 0x4000)
            ordinary = m.calls[boundary:]
            assert [c['call'] for c in ordinary] == ['write', 'upload', 'write', 'AStatus_newOk']
            assert bytes.fromhex(ordinary[1]['custom']) == struct.pack('<HH', 0, long_id)
            assert bytes.fromhex(ordinary[0]['data'])[16:] == struct.pack('<HHi', 21, 96, 100)
            assert bytes.fromhex(ordinary[2]['data'])[16:] == struct.pack('<HHi', 21, 7, 1)
            cases.append(dict(sample=sample, case=label, status='PASS', state=state,
                              plugin_calls=m.inits, plugin_boundaries=m.plugin_calls,
                              plugin_return=m.plugin_return,
                              symbols=m.symbols, calls=m.calls, ordinary_on=ordinary, logs=m.logs))
    files = [Path(__file__).resolve()] + [ROOT / 'tests' / (n + '.py') for n in
             ['haptics_service_init_review', 'haptics_service_route_review', 'haptics_driver_emulation',
              'haptics_service_request_emulation', 'haptics_playback_emulation', 'haptics_lifecycle_emulation']]
    files += [ROOT / 'tests/haptics-emulator-dependencies.json', ROOT / 'scripts/firmware_facts.py']
    report = dict(status='PASS', scope=__doc__, cases=cases, sources=sources,
                  tests={str(p.relative_to(ROOT)): sha(p) for p in files},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in DEPS.rglob('*')
                                  if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name)})
    (ROOT / 'logs/haptics-pcm-init-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'original PCM/data/AAC init cases; workers/thread/DSP/motor not executed')


if __name__ == '__main__':
    main()
