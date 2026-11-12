#!/usr/bin/env python3
"""Join original OS4 upload with stock-derived packed algorithm tables and bins.

Packed wmfw algorithm rows are decoded independently from original bytes and
supplied at the regmap-read boundary. Exact bin files pass original coefficient
parsing, identity/revision validation and raw-write code. This assumes those
registers expose the decoded table; no DSP executes and writes do not change
hardware. Mailbox/regmap/kernel services remain fixtures. Successful coefficient
paths stop at injected first MEM_RDY failure, without claiming DSP boot/motor.
"""
import json
from pathlib import Path
import struct
from haptics_upload_emulation import Upload, ROOT, DEPS, CTX, sha
from haptics_firmware_emulation import digest


def table(blob):
    p=40
    while p<len(blob):
        tag,n=struct.unpack_from('<II',blob,p)
        if tag==0x11000000:
            raw=blob[p+8:p+8+n];assert len(raw)%4==0
            stream=b''.join(raw[i:i+4][::-1] for i in range(0,len(raw),4))
            assert len(stream)%3==0
            words=[int.from_bytes(stream[i:i+3],'little') for i in range(0,len(stream),3)]
            cursor=3;hw={0x2800024:words[9]};rows=[];address=0x280000c
            for i in range(words[9]+1):
                row=words[cursor:cursor+6];assert len(row)==6
                hw.update(dict(zip(range(address,address+24,4),row)));rows.append(row)
                step=7 if i==0 else 6;cursor+=step;address+=step*4
            assert words[cursor]==0xbedead and [r[0] for r in rows]
            hw[address]=words[cursor]
            return hw,rows
        p+=8+((n+3)&~3)
    raise AssertionError('no packed table')


def bin_writes(blob,rows,reject_revision=False):
    assert blob[:4]==b'WMDR' and struct.unpack_from('<I',blob,4)[0]==16
    p=16;writes=[]
    while p<len(blob):
        offset,kind,aid,rev,rate,n=struct.unpack_from('<HHIIII',blob,p)
        raw=blob[p+20:p+20+n];assert len(raw)==n
        if kind in [5,6]:
            row=next(r for r in rows if r[0]&0xffff==aid&0xffff)
            assert row[1]==rev>>8
            if not reject_revision:
                address=(0x2800000+row[2]*4 if kind==5 else 0x3400000+row[4]*4)+offset
                for start in range(0,n,4096):
                    chunk=raw[start:start+4096]
                    writes.append(dict(address=address+start,length=len(chunk),sha256=digest(chunk)))
        else:assert kind==0xfe00
        p+=20+((n+3)&~3)
    assert p==len(blob)
    return writes


def exercise(path,blobs,filename):
    results=[];hardware,rows=table(blobs[filename])
    for label in ['stock-tables-and-bins','main-bin-missing','main-bin-invalid-revision','coefficient-first-write-error']:
        m=Upload(path,blobs,filename);m.hardware.update(hardware)
        if label=='main-bin-missing':m.missing={'cs40l26.bin'}
        if label=='main-bin-invalid-revision':
            desc=m.fwmap['cs40l26.bin'];addr=m.u64(desc+8)
            # First coefficient follows the 12-byte text region and its header.
            assert struct.unpack_from('<H',blobs['cs40l26.bin'],50)[0]==5
            m.uc.mem_write(addr+56,struct.pack('<I',0x7f000000))
        if label=='coefficient-first-write-error':m.raw_failure=len(m.facts['writes'])+1
        rc=m.run('cs40l26_fw_upload',CTX)
        assert rc==-5 and m.updates==[dict(address=0x2900,mask=2,value=2)]
        expected=list(m.facts['writes']);parameters=[]
        for name in m.requests[1:]:
            writes=bin_writes(blobs[name],rows,reject_revision=name=='cs40l26.bin' and label=='main-bin-invalid-revision')
            if name in m.missing:continue
            if label=='coefficient-first-write-error' and name=='cs40l26.bin':writes=writes[:1]
            parameters.extend(writes)
        expected+=parameters
        assert m.raw==expected,(filename,label,len(m.raw),len(expected))
        assert m.requests[0]==filename and len(m.requests)==(6 if filename=='cs40l26.wmfw' else 5)
        assert m.released==[m.fwmap[name] for name in m.requests if name not in m.missing]
        assert m.entries[-1]=='cs40l26_dsp_config' and m.uc.mem_read(CTX+0x1ca,1)==b'\0'
        if label=='stock-tables-and-bins':
            assert m.messages==['Failed to set MEM_RDY to initialize RAM\n']
            assert len(parameters)==(34 if filename=='cs40l26.wmfw' else 28)
        print(filename,label,'firmware',len(m.facts['writes']),'parameters',len(parameters),flush=True)
        results.append(dict(case=label,status='PASS',result=rc,requests=m.requests,released=m.released,
            algorithm_rows=rows,raw_writes=m.raw,parameter_writes=parameters,reads=m.reads,updates=m.updates,
            entries=m.entries,messages=m.messages,fw_loaded=0))
    return results


def main():
    prior=json.loads((ROOT/'logs/haptics-upload-emulation.json').read_text());cases=[];drivers={};sources={}
    for sample in ['os4-current','os4-stable']:
        record=prior['drivers'][sample];path=ROOT/record['path'];assert sha(path)==record['sha256'];drivers[sample]=record
        files=sorted((ROOT/'firmware/samples'/sample/'analysis/odm/firmware').glob('cs40l26*'))
        sources.update({str(p.relative_to(ROOT)):sha(p) for p in files})
        # Bind the disassembly produced by the upload suite, including original bin parser.
        disasm=ROOT/'logs'/f'{sample}-haptics-upload-core.disasm';sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        blobs={p.name:p.read_bytes() for p in files}
        for filename in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
            cases.extend(dict(sample=sample,firmware=filename,**c) for c in exercise(path,blobs,filename))
    assert len(cases)==16
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in ['haptics_upload_emulation.py',
        'haptics_firmware_emulation.py','haptics_driver_emulation.py','haptics-emulator-dependencies.json']]
    tests.append(ROOT/'scripts/firmware_facts.py')
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/haptics-coefficients-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':main()
