#!/usr/bin/env python3
"""Extract action-correlated observations from the user's second log batch.

No device access. Counters and driver messages are evidence of the stated
observations only; neither IRQ nor SPI DMA count proves packet validity.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FILES = ['touch-idle-irq.txt', 'touch-active.txt', 'touch-dmesg-before.txt',
         'touch-before.txt', 'touch-window.txt']


def decode(data):
    return data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff'))
                       else 'utf-8-sig')


def snapshots(value):
    result = []
    for line in value.splitlines():
        if re.fullmatch(r'\d+\.\d+\s+\d+\.\d+', line.strip()):
            result.append({'uptime': float(line.split()[0]), 'irqs': {}})
        elif result and line.split() and line.split()[-1] in ('spi_dma_irq', 'xiaomi_tpsynaptics_tcm'):
            fields = line.split()
            counts = []
            for item in fields[1:]:
                if not item.isdecimal():
                    break
                counts.append(int(item))
            assert counts
            result[-1]['irqs'][fields[-1]] = {'irq': fields[0].rstrip(':'), 'cpus': counts}
    assert len(result) == 2
    first, last = result
    duration = last['uptime'] - first['uptime']
    assert 0 < duration < 120
    deltas = {}
    for name in ('spi_dma_irq', 'xiaomi_tpsynaptics_tcm'):
        a, b = first['irqs'][name], last['irqs'][name]
        assert a['irq'] == b['irq'] and len(a['cpus']) == len(b['cpus'])
        assert all(y >= x for x, y in zip(a['cpus'], b['cpus']))
        delta = sum(b['cpus']) - sum(a['cpus'])
        deltas[name] = {'start': sum(a['cpus']), 'end': sum(b['cpus']),
                        'delta': delta, 'per_second': delta/duration}
    return {'snapshots': result, 'seconds': duration, 'irqs': deltas}


def main():
    data = {name: (ROOT/'imgs/built/1'/name).read_bytes() for name in FILES}
    text = {name: decode(value) for name, value in data.items()}
    idle = snapshots(text['touch-idle-irq.txt'])
    active = snapshots(text['touch-active.txt'])
    assert idle['irqs']['xiaomi_tpsynaptics_tcm']['delta'] == 0
    assert active['irqs']['xiaomi_tpsynaptics_tcm']['delta'] == 1613
    assert active['irqs']['spi_dma_irq']['delta'] == 1613
    assert 'Xiaomi_Touch_Input_0' in text['touch-active.txt']
    event_lines = [line for line in text['touch-active.txt'].splitlines()
                   if re.search(r'\bEV_(ABS|KEY|SYN)\b', line)]
    assert not event_lines
    boot = text['touch-dmesg-before.txt']
    keys = ['syna_tcm_v1_detect: Message including CRC:(no) extra RC:(no)',
            'Application Firmware (mode 0x1) activated',
            'syna_tcm_compare_image_id_info: No need to do reflash',
            'syna_dev_reflash_startup: Success to do reflash',
            'touch id 0 success register input dev',
            'syna_tcm_fw_version_read: is power off',
            'syna_set_ic_mode pwr_state is not PWR_ON',
            'CS40L26 ID: 0x40A260, Revision: 0xA1',
            'CS40L26 loaded with 43 RAM waveforms',
            'cs40l26_upload_worker: effect ID = 0 done, cs40l26->upload_ret = 0',
            'cs40l26_vibe_start_worker: effect ID = 0 done']
    matched = {}
    for key in keys:
        matched[key] = [line for line in boot.splitlines() if key in line]
        assert matched[key], key
    assert 'spi_dma_irq: inaccessible or not found' in text['touch-window.txt']
    report = {'status': 'OBSERVED', 'scope': __doc__.strip(),
              'files': {name: hashlib.sha256(value).hexdigest() for name, value in data.items()},
              'sources': {str(Path(__file__).relative_to(ROOT)):
                          hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
              'idle': idle, 'active': active, 'saved_input_event_lines': len(event_lines),
              'capture_exit_code': None,
              'capture_limit': 'Active file has before/after snapshots and device enumeration, but no getevent exit status. User reports no touch events; successful full-window capture cannot be independently proven from this file alone.',
              'boot_messages': matched,
              'failed_combined_command': 'PowerShell/adb quote loss made the regex alternation execute as a shell pipeline. Do not use that file as an IRQ window.',
              'touch_conclusion': 'Active window has matched +1613 touch/SPI DMA increments against idle +0, with no saved input events. Prioritize v1 report type/configuration and parse/input path; packet contents and valid controller replies remain unknown.',
              'haptics_conclusion': 'This boot reports A1 chip, 43 RAM waveforms and successful probe self-test upload/start software paths. Do not apply B2-only calibration conclusions or assume five waveforms. These messages do not prove motor output or GUI-request success.'}
    reviewed = ['scripts/collect-touch-v1-debug.sh', 'scripts/collect-touch-v1-debug.ps1',
                'logs/os4-stable-touch-loglevel.disasm', 'logs/os4-stable-touch-v1-field-path.disasm',
                'firmware/samples/os4-stable/analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko',
                'firmware/samples/os4-stable/analysis/vendor_dlkm/lib/modules/xiaomi_touch_dijun.ko']
    report['diagnostic_review_sources'] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                                           for name in reviewed}
    (ROOT/'logs/touch-action-runtime-observation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print('OBSERVED: idle +0; active touch/SPI +1613 / %.2fs; no saved events; v1 boot; haptics A1/43 waveforms' % active['seconds'])


if __name__ == '__main__':
    main()
