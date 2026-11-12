#!/usr/bin/env python3
"""Synthetic counter/event logs check triage, not touch hardware."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analysis', ROOT/'scripts/analyze_touch_window.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(root):
    for phase, start, end, first, last in [('idle', 10, 14, 3000, 3000),
                                          ('touch', 14, 26, 3000, 3020)]:
        for edge, uptime, count in [('start', start, first), ('end', end, last)]:
            (root/f'{phase}-{edge}-uptime.txt').write_text(f'{uptime}.00 0\n')
            (root/f'{phase}-{edge}-interrupts.txt').write_text(
                f'           CPU0 CPU1\n235: {count} 5 GICv3 77 Level spi_dma_irq\n'
                f'236: {count} 7 gpio 12 Level xiaomi_tpsynaptics_tcm\n')
        (root/f'{phase}-events.txt').write_text('add device 1: /dev/input/event3\n')
        (root/f'{phase}-getevent-exit.txt').write_text('137\n')


cases = []
for label in ['irq-without-events', 'no-irq', 'coordinates', 'capabilities-only',
              'reboot-counter', 'irq-renumbered', 'capture-error', 'missing',
              'utf16', 'overlap']:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); fixture(root)
        if label == 'no-irq':
            (root/'touch-end-interrupts.txt').write_bytes((root/'touch-start-interrupts.txt').read_bytes())
        elif label == 'coordinates':
            (root/'touch-events.txt').write_text('[ 15.123456] /dev/input/event3: EV_ABS ABS_MT_POSITION_X 0000fb90\n')
        elif label == 'capabilities-only':
            (root/'touch-events.txt').write_text('ABS_MT_POSITION_X : value 0, min 0, max 143999\n')
        elif label in ('reboot-counter', 'irq-renumbered'):
            p=root/'touch-end-interrupts.txt'
            p.write_text(p.read_text().replace('3020', '1') if label == 'reboot-counter'
                         else p.read_text().replace('236:', '240:'))
        elif label == 'capture-error':
            (root/'touch-getevent-exit.txt').write_text('1\n')
        elif label == 'missing':
            (root/'touch-start-interrupts.txt').unlink()
        elif label == 'utf16':
            for p in root.iterdir(): p.write_bytes(p.read_text().encode('utf-16'))
        elif label == 'overlap':
            (root/'touch-start-uptime.txt').write_text('13 0\n')
        result=module.analyze(root)
        bad=label in ('reboot-counter','irq-renumbered','capture-error','missing','overlap')
        assert result['status']==('insufficient' if bad else 'observed'), (label,result)
        if not bad:
            assert result['touch']['coordinate_event_count']==(1 if label=='coordinates' else 0)
            assert result['touch']['irqs']['xiaomi_tpsynaptics_tcm']['delta']==(0 if label=='no-irq' else 20)
            assert result['idle']['irqs']['xiaomi_tpsynaptics_tcm']['delta']==0
        cases.append({'case':label, 'result':result})
report={'status':'PASS','scope':__doc__,'count':len(cases),'cases':cases,
        'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [Path(__file__), ROOT/'scripts/analyze_touch_window.py',
                              ROOT/'scripts/collect-touch-no-events.sh',
                              ROOT/'scripts/collect-touch-no-events.ps1']}}
(ROOT/'logs/touch-window-analysis-test.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS',len(cases),'synthetic triage cases')
