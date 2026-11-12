#!/usr/bin/env python3
"""Check actual-image Cirrus firmware bytes at substituted module insertion.

Runs shipped cache/modules scripts with real profile/OTA/CAS bytes. Mounts,
properties, insmod and device nodes remain private fixtures. Tests remove stock
firmware trees after cache to model unavailability, not a kernel unmount.
Original parser metadata names the vendor/ODM parameter differences; no DSP,
kernel firmware loader, physical probe or motor executes.
"""
import hashlib
import json
from pathlib import Path
import shutil
import stat
import struct
import tempfile

import profile_runtime_test as runtime
from haptics_calibration_coefficients_emulation import Calibration
from haptics_coefficients_emulation import table
from haptics_driver_emulation import ROOT,DEPS,sha
from firmware_facts import boot_parts,ramdisk_entries

FILES={'cs40l26-a2h.bin','cs40l26-a2h1.bin','cs40l26-calib.bin','cs40l26-calib.wmfw',
       'cs40l26-dbc.bin','cs40l26-dvl.bin','cs40l26-svc.bin','cs40l26.bin','cs40l26.wmfw'}

def words(blob,rows):
    assert blob[:4]==b'WMDR' and struct.unpack_from('<I',blob,4)[0]==16
    out={};pos=16
    while pos<len(blob):
        delta,kind,aid,rev,rate,n=struct.unpack_from('<HHIIII',blob,pos)
        assert pos+20+n<=len(blob)
        if kind in [5,6]:
            row,=[r for r in rows if r[0]&0xffff==aid&0xffff]
            assert row[1]==rev>>8 and n%4==0
            base=(0x2800000+row[2]*4 if kind==5 else 0x3400000+row[4]*4)+delta
            for i in range(0,n,4):
                assert base+i not in out
                out[base+i]=int.from_bytes(blob[pos+20+i:pos+24+i],'big')
        else:assert kind==0xfe00
        pos+=20+((n+3)&~3)
    assert pos==len(blob)
    return out

def parameter_differences():
    results={};sources={}
    for sample in ['os4-current','os4-stable']:
        base=ROOT/'firmware/samples'/sample/'analysis'
        driver=base/'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        fw=base/'odm/firmware/cs40l26.wmfw'
        m=Calibration(driver,fw.read_bytes());records=m.records();rows=table(fw.read_bytes())[1]
        rc=base/'system-resources/system/system/etc/ueventd.rc'
        line,=[s for s in rc.read_text().splitlines() if s.startswith('firmware_directories ')]
        order=line.split()[1:];assert order.index('/odm/firmware/')<order.index('/vendor/firmware/')
        sources.update({str(p.relative_to(ROOT)):sha(p) for p in [driver,fw,rc]})
        differences={}
        for name in ['cs40l26-a2h.bin','cs40l26-dbc.bin']:
            paths=[base/part/'firmware'/name for part in ['vendor','odm']]
            sources.update({str(p.relative_to(ROOT)):sha(p) for p in paths})
            vendor,odm=[words(p.read_bytes(),rows) for p in paths]
            assert vendor.keys()==odm.keys()
            differences[name]=[dict(address=a,vendor=vendor[a],odm=odm[a],
                coefficient_names=[r['name'] for r in records if r['register']==a])
                for a in vendor if vendor[a]!=odm[a]]
        assert len(differences['cs40l26-a2h.bin'])==8 and len(differences['cs40l26-dbc.bin'])==2
        assert {c['coefficient_names'][0] for c in differences['cs40l26-dbc.bin']}=={'DBC_RISE_HEADROOM','DBC_FALL_HEADROOM'}
        results[sample]=dict(firmware_directories=order,differences=differences)
    return results,sources

def main():
    index=json.loads((ROOT/'simulation-report.json').read_text());image=Path(index['image'])
    assert sha(image)==index['image_sha256']
    runtime.IMAGE_SHA=sha(image)
    runtime.IMAGE_ENTRIES={e[0]:e for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    cases=[];sources={}
    with tempfile.TemporaryDirectory(prefix='haptics-image-cas-') as temp:
        runtime.IMAGE_CAS=Path(temp)
        for name,entry in runtime.IMAGE_ENTRIES.items():
            if name.startswith('system/etc/dijun/blobs/') and stat.S_ISREG(entry[1]):
                assert hashlib.sha256(entry[-1]).hexdigest()==Path(name).name
                (runtime.IMAGE_CAS/Path(name).name).write_bytes(entry[-1])
        for sample in runtime.SAMPLES:
            for slot in ['_a','_b']:
                fixture=runtime.Runtime()
                try:
                    root=fixture.fixture(sample,slot,preloaded=False)
                    profile=json.loads((runtime.CATALOG/sample/'profile.json').read_text())
                    expected={Path(name).name:item['sha256'] for name,item in profile['assets'].items()
                              if name.startswith('lib/firmware/cs40l26')}
                    assert set(expected)==FILES
                    (root/'firmware-expected.json').write_text(json.dumps(expected))
                    mock=root/'mockbin/insmod'
                    text=mock.read_text().replace("assert (r/'lib/firmware/cs40l26.wmfw').is_file(), 'firmware must precede insmod'",'''import hashlib
    expected=json.loads((r/'firmware-expected.json').read_text())
    assert (r/'sys/module/firmware_class/parameters/path').read_text().strip()=='/lib/firmware'
    observed={name:hashlib.sha256((r/'lib/firmware'/name).read_bytes()).hexdigest() for name in expected}
    assert observed==expected, 'all nine ODM firmware files must match before every insertion'
    with (r/'firmware-observations.jsonl').open('a') as output:
        output.write(json.dumps(dict(module=module,files=observed))+'\\n')''')
                    assert 'all nine ODM' in text
                    mock.write_text(text)
                    fixture.run_phase(root,'cache')
                    for part in ['vendor','odm']:
                        shutil.rmtree(root/part/'firmware',ignore_errors=True)
                    fixture.unmount(root)
                    fixture.run_phase(root,'modules',HAPTICS_INPUT='immediate')
                    observations=[json.loads(s) for s in (root/'firmware-observations.jsonl').read_text().splitlines()]
                    plan=json.loads((runtime.CATALOG/sample/'module-sources.json').read_text())
                    assert [v['module'] for v in observations]==plan['order']
                    assert fixture.props(root)['twrp.profile.haptics_input']=='registered'
                    assert fixture.props(root)['twrp.profile.modules']=='complete'
                    assert {n:sha(root/'lib/firmware'/n) for n in expected}==expected
                    for name in expected:
                        stock=ROOT/'firmware/samples'/sample/'analysis/odm/firmware'/name
                        assert sha(stock)==expected[name]
                        sources[str(stock.relative_to(ROOT))]=sha(stock)
                    cases.append(dict(sample=sample,slot=slot,status='PASS',
                                      verified_files=expected,module_boundary_observations=observations,
                                      stock_firmware_removed=True,firmware_path='/lib/firmware'))
                    print('PASS',sample,slot,len(observations),'module boundaries,9 firmware hashes each',flush=True)
                finally:fixture.doCleanups()
    differences,extra=parameter_differences();sources.update(extra)
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in ['profile_runtime_test.py','profile_selection_test.py',
        'haptics_calibration_coefficients_emulation.py','haptics_firmware_emulation.py',
        'haptics_coefficients_emulation.py','haptics_driver_emulation.py','haptics_upload_emulation.py',
        'haptics-emulator-dependencies.json']]+[ROOT/'scripts/firmware_facts.py',ROOT/'scripts/acquire_firmware.py']
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    report=dict(status='PASS',scope=__doc__,image_sha256=sha(image),cases=cases,
                parameter_differences=differences,sources=sources,
                shipped_scripts={n:hashlib.sha256(e[-1]).hexdigest() for n,e in runtime.IMAGE_ENTRIES.items()
                                 if n.startswith('system/bin/dijun-') and n.endswith('.sh')},
                tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
                emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps})
    (ROOT/'logs/haptics-firmware-publication.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS:12 profile/slot activations; original ODM/vendor differences retained; no physical readiness claim')

if __name__=='__main__':main()
