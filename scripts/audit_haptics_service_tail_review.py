#!/usr/bin/env python3
"""Bind original service thread/XML/idle-PCM evidence to the current image.

Recorded ALSA/socket success is a fixture, not working hardware or DSP proof.
"""
import hashlib
import json
import struct
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = ROOT / 'logs/haptics-service-tail-review.json'
    report = json.loads(evidence.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 14
    for group in ['sources', 'tests', 'emulator_files']:
        assert report[group]
        for name, digest in report[group].items():
            assert sha(ROOT / name) == digest, name
    labels = {'normal', 'xml-absent', 'xml-no-long', 'xml-long42', 'thread-run-error',
              'pcm-array-error', 'audio-socket-timeout'}
    for sample in ['os4-current', 'os4-stable']:
        cases = {c['case']: c for c in report['cases'] if c['sample'] == sample}
        assert cases.keys() == labels
        xml = ET.fromstring((ROOT / 'firmware/samples' / sample / 'analysis/odm/etc/waveform_conf.xml').read_bytes())
        mapping = xml.find('waveform_id_mapping')
        expected_map = {int(k.text): int(v.text) for k, v in zip(mapping.findall('key'), mapping.findall('value'))}
        for label, case in cases.items():
            assert case['status'] == 'PASS'
            state = case['state']
            assert state['selector'] == 1 and state['sample_rate'] == 48000
            assert state['protect_ms'] == 20 and state['low_power'] == 1
            assert state['buffer_samples'] == 3840
            expected_long = 42 if label == 'xml-long42' else (35 if label in ['xml-absent', 'xml-no-long'] else 31)
            assert state['long_id'] == expected_long
            if label == 'xml-absent':
                assert state['containers'] == dict(mapping={}, no_dvl={}, no_svc={})
            else:
                assert {int(k): v for k, v in state['containers']['mapping'].items()} == expected_map
                for name in ['no_dvl', 'no_svc']:
                    assert set(map(int, state['containers'][name])) == set(map(int, xml.findtext(name + '/data').split(',')))
            assert len(case['run_requests']) == 1
            assert case['run_requests'][0]['result'] == (-11 if label == 'thread-run-error' else 0)
            assert case['run_requests'][0]['callback_executed'] is False
            tail = [c for c in case['calls'] if c.get('phase') == 'startup-tail']
            assert [c['args'][1] for c in tail if c['call'] == 'pthread_condattr_setclock'] == [1]
            assert len([c for c in tail if c['call'] == 'xmlFreeDoc']) == int(label != 'xml-absent')
            assert not any(c['call'] in ['mixer_ctl_set_value', 'pcm_open', 'write', 'ioctl'] for c in tail)
            worker = case['worker']
            if label == 'thread-run-error':
                assert not worker and not case['peer_messages'] and case['pcm_config'] is None
            else:
                assert worker[-1]['call'] == 'pthread_cond_timedwait' and worker[-1]['deadline'] == [102, 0]
                expected_controls = [] if label == 'pcm-array-error' else [
                    ('Haptics Source', 1), ('ASP Mode', 1), ('ASP PCM Slot', 1),
                    ('audio_tdm_fmtchs', 8), ('XR_TDM7_RX Mixer XR_media7', 1)]
                assert [(c['control'], c['value']) for c in worker if c['call'] == 'mixer_ctl_set_value'] == expected_controls
                arrays = [c for c in worker if c['call'] == 'mixer_ctl_set_array']
                assert len(arrays) == 1 and arrays[0]['values'] == [48000, 24, 4]
                assert arrays[0]['result'] == (-5 if label == 'pcm-array-error' else 0)
                assert case['pcm_config'] == [1, 48000, 480, 4, 3, 120, 2147483647, 120]
                assert len([c for c in worker if c['call'] == 'pcm_open']) == 1
                assert [c['bytes'] for c in worker if c['call'] == 'original-pcm-frames-return'] == [4096]
                assert len(case['peer_messages']) == (2 if label == 'audio-socket-timeout' else 1)
                for message in case['peer_messages']:
                    assert bytes.fromhex(message) == struct.pack('<III', 42, 1, 1) + bytes(60)
                assert [c['result'] for c in worker if c['call'] == 'poll'] == ([0, 0] if label == 'audio-socket-timeout' else [1])
            ordinary = case['ordinary_on']
            assert [c['call'] for c in ordinary] == ['_ZN7android7MiEventC1Ej', 'write', 'upload', 'write',
                                                    '_ZN7android7MiEventD1Ev', 'AStatus_newOk']
            assert bytes.fromhex(ordinary[2]['custom']) == struct.pack('<HH', 0, expected_long)
            assert bytes.fromhex(ordinary[1]['data'])[16:] == struct.pack('<HHi', 21, 96, 100)
            assert bytes.fromhex(ordinary[3]['data'])[16:] == struct.pack('<HHi', 21, 7, 1)
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    entry, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS4-haptics-service-tail-review']
    assert entry['evidence_sha256'] == sha(evidence) and entry['count'] == 14
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    source = json.loads(image.with_name(image.stem + '-sources.json').read_text())
    assert source['image_sha256'] == index['image_sha256']
    for name, digest in source['files'].items():
        assert sha(Path(name)) == digest, name
    for name, target in source['symlinks'].items():
        assert str(Path(name).readlink()) == target, name
    result = dict(status='PASS', scope=__doc__, cases=14, production_changed=False,
                  field_vibration='unresolved', evidence_sha256=sha(evidence),
                  image_sha256=index['image_sha256'], production_source_files=len(source['files']),
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md', 'MAINTENANCE.md',
                             'simulation-report.md', 'simulation-report.json', 'docs/HAPTICS-ADAPTATION.md',
                             'docs/HAPTICS-SERVICE-THREAD-XML.md', 'docs/HAPTICS-PCM-INITIALIZATION.md']},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-service-tail-review-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:14 original thread/XML/PCM idle-start cases; current image/source binding; physical vibration unresolved')


if __name__ == '__main__':
    main()
