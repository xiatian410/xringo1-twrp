#!/usr/bin/env python3
"""Execute production sparse-image entry with real AOSP sparse parser/writer.

All I/O stays in disposable ordinary files. fstat/BLKGETSIZE64/ftruncate describe
one file as a block target; discard is a recorded no-op. Size discovery is a
fixture, raw routing intentionally not run. No manager/GUI/slot/USB execution,
physical block I/O, target ARM64 execution or power-loss durability proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from nested_partition_path_test import method, ROOT, SRC

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=SRC/'partition.cpp')
    ap.add_argument('--report',type=Path,default=ROOT/'logs/sparse-flash.json')
    args=ap.parse_args()
    sparse=SRC.parents[1]/'system/core/libsparse'
    base=SRC.parents[1]/'system/libbase'
    sources=[sparse/(n+'.cpp') for n in ['backed_block','output_file','sparse','sparse_crc32','sparse_err','sparse_read']]
    sources += [base/'mapped_file.cpp',base/'stringprintf.cpp']
    text=args.source.read_text()
    bodies='\n'.join(method(text,s) for s in ['bool TWPartition::FlashImage(',
                     'bool TWPartition::IsSparseImage(', 'bool TWPartition::FlashSparseImage('])
    cases=[]; commands=[]
    with tempfile.TemporaryDirectory(prefix='sparse-flash-') as tmp:
        work=Path(tmp)
        harness=work/'test.cpp'
        harness.write_text((ROOT/'tests/sparse_flash_test.cpp').read_text().replace('// PRODUCTION_METHODS',bodies))
        names=['normal','expanded-oversize','cached-small','actual-small','capacity-error','capacity-eintr',
               'zero-capacity','regular-target','sync-error','sync-eintr','close-error','write-error',
               'write-late-error','write-eintr','write-short',
               'bad-chunk','zero-blocks','files-target','disabled-target','missing-source']
        for discard in [False,True]:
            exe=work/('test-discard' if discard else 'test')
            cmd=['g++','-std=c++23','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all',
                 '-fno-omit-frame-pointer','-no-pie','-I'+str(base/'include'),'-I'+str(sparse/'include'),
                 '-I'+str(sparse),str(harness),*map(str,sources),'-lz',
                 *['-Wl,--wrap='+n for n in ['fstat','ioctl','write','fsync','close','ftruncate64']],'-o',str(exe)]
            if discard: cmd.insert(1,'-DTW_ENABLE_BLKDISCARD')
            subprocess.run(cmd,check=True);commands.append(cmd)
            for name in names:
                wd=work/(name+('-discard' if discard else ''));wd.mkdir()
                def chunk(kind,blocks,payload=b''):
                    return struct.pack('<HHII',kind,0,blocks,len(payload)+12)+payload
                raw=bytes((i*31+19)%251 for i in range(4096))
                fill=struct.pack('<I',0x12345678)
                if name=='expanded-oversize':
                    chunks=[chunk(0xcac2,16,fill)];blocks=16
                elif name=='zero-blocks':
                    chunks=[];blocks=0
                else:
                    chunks=[chunk(0xcac1,1,raw),chunk(0xcac2,1,fill),chunk(0xcac3,1),chunk(0xcac1,1,raw[::-1])];blocks=4
                payload=struct.pack('<IHHHHIIII',0xed26ff3a,1,0,28,12,4096,blocks,len(chunks),0)+b''.join(chunks)
                if name=='bad-chunk':payload=payload[:28]+chunk(0xdead,4)
                image=wd/'input.sparse';image.write_bytes(payload)
                target=wd/'target.bin';sentinel=b'\xa5'*32768;target.write_bytes(sentinel)
                expected=name in ['normal','capacity-eintr','sync-eintr','write-eintr','write-short']
                run=subprocess.run([str(exe),name,str(int(expected))],cwd=wd,capture_output=True,text=True,timeout=15)
                after=target.read_bytes()
                unchanged=name in ['expanded-oversize','cached-small','actual-small','capacity-error','zero-capacity',
                                  'regular-target','bad-chunk','zero-blocks','files-target','disabled-target','missing-source','write-error']
                content_ok=after==sentinel if unchanged else after==raw+fill*1024+sentinel[8192:12288]+raw[::-1]+sentinel[16384:]
                if name=='write-late-error': content_ok=after==raw+sentinel[4096:]
                passed=run.returncode==0 and content_ok
                cases.append(dict(case=name,discard_build=discard,status='PASS' if passed else 'FAIL',
                                  exit=run.returncode,content_ok=content_ok,input_size=len(payload),
                                  expanded_size=blocks*4096,target_size=len(after),target_sha256=sha(target),
                                  output=run.stdout+run.stderr))
                print(cases[-1]['status'],name,'discard='+str(discard),flush=True)
    bound=sources+[args.source,Path(__file__).resolve(),ROOT/'tests/sparse_flash_test.cpp']
    bound+=list((sparse/'include').rglob('*.h'))+list(sparse.glob('*.h'))
    bound+=[base/'include/android-base'/n for n in ['unique_fd.h','scopeguard.h','mapped_file.h','stringprintf.h']]
    report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,
                cases=cases,compile_commands=commands,sources={str(p):sha(p) for p in bound})
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'

if __name__=='__main__': raise SystemExit(main())
