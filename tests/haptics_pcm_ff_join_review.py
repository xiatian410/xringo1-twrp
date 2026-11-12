#!/usr/bin/env python3
"""Join original codec/control/DAI/PCM widget setup to production A1 FF.

Original codec driver/component probe, ASP Mode1/PCM Slot1 setters, hw_params,
asp_params/clk_en/asp_rx and FF callbacks/workers/IRQ execute in one VM.
MFD/ALSA pointers, register services, codec allocation/registration, format-width
lookup/string comparison, hw_params memory (48kHz/S24_LE/one or two channels), PM/mailbox/timeouts,
serial widget order/queues and supplied IRQ messages are explicit fixtures.
The stock service front end is mono; real backend negotiation is not executed.
There is no physical clock, ALSA dispatcher/DAPM, DSP or motor execution.
"""
import inspect
import json
from pathlib import Path
import subprocess
import tempfile

from haptics_asp_ff_join_review import ASP
from haptics_a1_joined_review import ROOT, CTX, INPUT, EFFECT, EFFECTS
from haptics_driver_emulation import (SOURCE, DEPS, sha, capture, MASK,
                                      UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30)

SCRATCH = 0x4400000
WIDGET, COMPONENT, DEVICE, CODEC = SCRATCH, SCRATCH + 0x1000, SCRATCH + 0x2000, SCRATCH + 0x3000
DAI, CONTROL, VALUE, PARAMS = SCRATCH + 0x5000, SCRATCH + 0x6000, SCRATCH + 0x7000, SCRATCH + 0x8000


class PCM(ASP):
    def __init__(self, *args):
        self.pcm_phase = None
        self.pcm_updates, self.pcm_boundaries, self.pcm_entries = [], [], []
        super().__init__(*args)
        # Keep codec/DAI fixtures disjoint from stock firmware descriptors/data
        # below0x4100000, allocator0x4100000..0x4200000 and firmware0x4300000.
        self.uc.mem_map(SCRATCH, 0x10000)

    def on_code(self, u, address, size, data):
        if self.pcm_phase is None:
            return super().on_code(u, address, size, data)
        for name in ['cs40l26_codec_driver_probe', 'cs40l26_codec_probe', 'cs40l26_asp_mode_put',
                     'cs40l26_asp_pcm_slot_put', 'cs40l26_set_tdm_slot', 'cs40l26_pcm_hw_params',
                     'cs40l26_component_set_sysclk', 'cs40l26_asp_params', 'cs40l26_asp_rx']:
            if address == self.symbols[name]:
                self.pcm_entries.append(dict(phase=self.pcm_phase, function=name))
        name = self.hooks.get(address)
        a = [self.arg(i) for i in range(7)] if name else []
        if name == 'devm_kmalloc' and self.pcm_phase == 'codec-driver':
            assert a[:3] == [DEVICE, 96, 0xdc0]
            u.mem_write(CODEC, bytes(96))  # GFP_ZERO semantics of original request.
            result = CODEC
        elif name == 'snd_soc_dapm_to_component':
            assert a[0] == WIDGET + 0x4000
            result = COMPONENT
        elif name == 'snd_soc_register_component':
            assert self.pcm_phase == 'codec-driver' and a[0] == DEVICE
            assert a[2] == self.symbols['cs40l26_dai'] and a[3] == 1
            result = 0
        elif name == 'snd_pcm_format_width':
            assert self.pcm_phase == 'hw-params' and a[0] == 6
            result = 24  # Reviewed SNDRV_PCM_FORMAT_S24_LE, not tinyalsa enum3.
        elif name == 'strcmp':
            assert self.pcm_phase in ['controls', 'params']
            left, right = self.string(a[0]), self.string(a[1])
            assert left == right == self.string(self.u64(DAI))
            result = 0
        elif name == 'regmap_update_bits_base' and self.pcm_phase in ['params', 'rx']:
            assert a[0] == 0x4070000
            failed = (self.case == 'params-all-writes-error' and self.pcm_phase == 'params' or
                      self.case == 'rx-first-write-error' and self.pcm_phase == 'rx' and a[1] == 0x4c00 or
                      self.case == 'rx-last-write-error' and self.pcm_phase == 'rx' and a[1] == 0x4800)
            result = -5 if failed else 0
            self.pcm_updates.append(dict(phase=self.pcm_phase, address=a[1], mask=a[2], value=a[3], result=result))
        else:
            return super().on_code(u, address, size, data)
        self.pcm_boundaries.append(dict(phase=self.pcm_phase, function=name, result=result))
        self.calls.append(name)
        u.reg_write(UC_ARM64_REG_X0, result & MASK)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))

    def setup(self, case):
        self.case = case
        self.asp_runtime = self.runtime = True
        self.scenario = 'no-ASP'
        self.hardware[0x2c04] = 0
        self.put32(CTX + 0x200, 0)
        self.put32(CTX + 0x1d0, 0)
        self.completed.clear()
        self.selftest_writes.clear()
        self.selftest_mail.clear()
        assert self.u32(CTX + 0x1bb0) == 100
        assert self.uc.mem_read(CTX + 0x1d5, 1) == b'\0'
        self.put64(WIDGET + 0x28, WIDGET + 0x4000)
        self.put64(COMPONENT + 0x10, DEVICE)
        self.put64(DEVICE + 0x60, 0x4060000)
        self.put64(0x4060000 + 0x98, CTX)
        self.put64(COMPONENT + 0x60, DAI + 0x68)
        self.put64(DAI + 0x60, COMPONENT)
        rodata = next(self.bases[i] for i, s in enumerate(self.sections) if s.name == '.rodata')
        self.put64(DAI, rodata + 0x43df)
        self.put64(CONTROL + 0x80, COMPONENT)
        self.put32(VALUE + 0x48, 1)
        results = {}
        self.pcm_phase = 'codec-driver'
        results['codec_driver_probe'] = self.runtime_call('cs40l26_codec_driver_probe', DEVICE - 0x10)
        assert self.u64(DEVICE + 0x98) == CODEC
        self.pcm_phase = 'codec-component'
        results['codec_probe'] = self.runtime_call('cs40l26_codec_probe', COMPONENT)
        assert self.u32(CODEC + 0x18) == 1536000
        self.pcm_phase = 'controls'
        results['mode'] = self.runtime_call('cs40l26_asp_mode_put', CONTROL, VALUE)
        results['slot'] = self.runtime_call('cs40l26_asp_pcm_slot_put', CONTROL, VALUE)
        assert [self.u32(CODEC + x) for x in [0x30, 0x34, 0x38, 0x3c, 0x40]] == [0, 0, 2, 2, 3]
        self.put32(PARAMS + 0x24, 1 << 6)
        self.put32(PARAMS + 0x11c, 2 if case == 'two-channel-backend-fixture' else 1)
        self.put32(PARAMS + 0x128, 48000)
        self.pcm_phase = 'hw-params'
        results['hw_params'] = self.runtime_call('cs40l26_pcm_hw_params', 0, PARAMS, DAI)
        assert all(v == 0 for v in results.values()), results
        assert [self.u32(CODEC + x) for x in [0x4c, 0x50, 0x54]] == [48000, 24, 32]
        assert self.u32(CODEC + 0x18) == (3072000 if case == 'two-channel-backend-fixture' else 1536000)
        if case != 'no-widgets':
            self.pcm_phase = 'params'
            results['asp_params'] = self.runtime_call('cs40l26_asp_params', WIDGET, 0, 2)
            assert results['asp_params'] == 0
            self.pcm_phase = 'clock'
            results['clk_en'] = self.runtime_call('cs40l26_clk_en', WIDGET, 0, 2)
            assert results['clk_en'] == 0
            self.pcm_phase = 'rx'
            results['asp_rx'] = self.runtime_call('cs40l26_asp_rx', WIDGET, 0, 2)
            assert results['asp_rx'] == (-5 if case.startswith('rx-') else 0)
            expected = [(0x4008, 0x10000, 0), (0x4840, 0x3f, 24),
                        (0x4808, 0xff000744, 0x20000000), (0x4820, 0x3f3f, 0x302)]
            assert [(w['address'], w['mask'], w['value']) for w in self.pcm_updates if w['phase'] == 'params'] == expected
            rx = [(0x4c00, 0x7f, 50), (0x4c20, 0x7f, 50), (0x4800, 0x30003, 0x30003)]
            assert [(w['address'], w['mask'], w['value']) for w in self.pcm_updates if w['phase'] == 'rx'] == (rx[:1] if case == 'rx-first-write-error' else rx), (case, self.pcm_updates)
            assert sum(w['result'] != 0 for w in self.pcm_updates) == (4 if case == 'params-all-writes-error' else int(case.startswith('rx-')))
        else:
            assert not self.pcm_updates and not self.asp_mail
        return results


def main():
    dtpath = ROOT / 'logs/haptics-devicetree-audit.json'
    dt = json.loads(dtpath.read_text())
    sources = {str(dtpath.relative_to(ROOT)): sha(dtpath)}
    prior_path = ROOT / 'logs/haptics-service-tail-review.json'
    prior = json.loads(prior_path.read_text())
    assert prior['status'] == 'PASS'
    sources[str(prior_path.relative_to(ROOT))] = sha(prior_path)
    asound = Path('/root/AAA/twrp/bionic/libc/kernel/uapi/sound/asound.h')
    assert '#define SNDRV_PCM_FORMAT_S24_LE (( snd_pcm_format_t) 6)' in asound.read_text()
    sources[str(asound)] = sha(asound)
    for group in ['sources', 'libfdt_sources']:
        for name, digest in dt[group].items():
            p = Path(name) if Path(name).is_absolute() else ROOT / name
            assert sha(p) == digest
            sources[str(p)] = digest
    cases = []
    with tempfile.TemporaryDirectory(prefix='dijun-pcm-ff-') as temp:
        effect = next(e for n, e, event in capture(Path(temp)) if n == 80)
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        driver = base / 'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        assert sha(driver) == '969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6'
        files = sorted((base / 'odm/firmware').glob('cs40l26*'))
        blobs = {p.name: p.read_bytes() for p in files}
        service, = [c for c in prior['cases'] if c['sample'] == sample and c['case'] == 'normal']
        assert service['pcm_config'][:2] == [1, 48000] and service['pcm_config'][4] == 3
        props = next(c for c in dt['cases'] if c['sample'] == sample and c['case'] == 'overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
        ds = ROOT / 'logs' / (sample + '-haptics-pcm-ff-core.disasm')
        names = ['cs40l26_codec_driver_probe', 'cs40l26_codec_probe', 'cs40l26_asp_mode_put',
                 'cs40l26_asp_pcm_slot_put', 'cs40l26_set_tdm_slot', 'cs40l26_pcm_hw_params',
                 'cs40l26_component_set_sysclk', 'cs40l26_asp_params', 'cs40l26_asp_rx']
        ds.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-dr',
            '--disassemble-symbols=' + ','.join(names), str(driver)]))
        for p in files + [driver, ds]: sources[str(p.relative_to(ROOT))] = sha(p)
        for label in ['no-widgets', 'mono-front-end-shaped-fixture', 'two-channel-backend-fixture',
                      'params-all-writes-error', 'rx-first-write-error', 'rx-last-write-error']:
            m = PCM(driver, blobs, props, 'A1')
            assert all(p + len(blobs[n]) + 32 < 0x4100000 < SCRATCH for n, p in m.fwmap.items())
            assert m.run('cs40l26_probe', CTX) == 0
            results = m.setup(label)
            codec = {hex(offset): m.u32(CODEC + offset) for offset in [0x18, 0x30, 0x34, 0x38, 0x3c, 0x40, 0x4c, 0x50, 0x54]}
            m.pcm_phase = 'FF'
            m.uc.mem_write(EFFECT, effect)
            m.uc.mem_write(EFFECTS + 7 * 48, effect)
            assert m.runtime_call('cs40l26_upload_effect', INPUT, EFFECT, 0) == 0
            assert m.runtime_call('cs40l26_playback_effect', INPUT, 7, 1) == 0
            m.flush_until(CTX + 0xc0)
            assert m.selftest_mail == [dict(command=0x1800081, result=0)]
            assert [(w['address'], w['value'], w['result']) for w in m.selftest_writes] == [
                (0x280701c, 20, 0), (0x2807014, 125, 0), (0x2807018, 64, 0), (0x2802134, 80, 0), (0x28059f0, 0, 0)]
            for message in [0x01000010, 0x01000000]:
                m.supply([message])
                assert m.runtime_call('cs40l26_handle_mbox_buffer', 123, CTX) == 1
            assert m.state() == dict(vibe_state=0 if label == 'no-widgets' else 2, count=0, asp_active=int(label != 'no-widgets'))
            assert m.u32(CTX + 0x228) == 0xffffffff and not m.locked and not m.queue
            cases.append(dict(sample=sample, case=label, status='PASS', setup_results=results, codec_cache=codec,
                              PCM_updates=m.pcm_updates, PCM_entries=m.pcm_entries, boundaries=m.pcm_boundaries,
                              FF_writes=m.selftest_writes, FF_mailbox=m.selftest_mail, final_state=m.state(),
                              waveform_complete_counter=m.u32(CTX + 0x228)))
            print(sample, label, results, flush=True)
    for p in [SOURCE, SOURCE.with_suffix('.h'), ROOT / 'tests/haptics_driver_capture.cpp']:
        sources[str(p)] = sha(p)
    tests = {str(Path(__file__).resolve().relative_to(ROOT)): sha(Path(__file__))}
    for cls in PCM.mro():
        if cls is object: continue
        p = Path(inspect.getfile(cls)).resolve()
        tests[str(p.relative_to(ROOT))] = sha(p)
    for p in [ROOT / 'tests/haptics_coefficients_emulation.py', ROOT / 'tests/haptics-emulator-dependencies.json', ROOT / 'scripts/firmware_facts.py']:
        tests[str(p.relative_to(ROOT))] = sha(p)
    report = dict(status='PASS', scope=__doc__, cases=cases, production_effect=effect.hex(),
                  sources=sources, tests=tests, emulator_files={str(p.relative_to(ROOT)): sha(p) for p in DEPS.rglob('*')
                  if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name)})
    (ROOT / 'logs/haptics-pcm-ff-join-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'original PCM/FF joined cases; physical output unverified')


if __name__ == '__main__': main()
