#!/usr/bin/env python3
"""Apply every original DTBO entry to its matching base DTB; inspect haptics.

Uses AOSP libfdt on host files only. No bootloader board selection, device probe,
overlay writeback, calibration or physical I2C operation is performed.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from firmware_facts import ROOT, SAMPLES, boot_parts

DTC_SOURCE = Path('/root/AAA/twrp/external/dtc')
LIB_FILES = ['fdt.c','fdt_ro.c','fdt_wip.c','fdt_sw.c','fdt_rw.c','fdt_strerror.c',
             'fdt_empty_tree.c','fdt_addresses.c','fdt_overlay.c']

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def align(value): return (value+3) & ~3


def nodes(blob):
    header = struct.unpack_from('>10I',blob)
    assert header[0] == 0xd00dfeed and header[1] <= len(blob)
    strings = blob[header[3]:header[3]+header[8]]
    position, end = header[2], header[2]+header[9]
    assert end <= header[1] and len(strings) == header[8]
    stack, result = [], {}
    while position < end:
        token, = struct.unpack_from('>I',blob,position)
        position += 4
        if token == 1:
            terminator = blob.index(b'\0',position,end)
            stack.append(blob[position:terminator].decode())
            position = align(terminator+1)
            result['/'+'/'.join(stack[1:])] = {}
        elif token == 2:
            assert stack
            stack.pop()
        elif token == 3:
            length, offset = struct.unpack_from('>II',blob,position)
            position += 8
            assert offset < len(strings) and position+length <= end
            name = strings[offset:strings.index(b'\0',offset)].decode()
            path = '/'+'/'.join(stack[1:])
            assert name not in result[path]
            result[path][name] = blob[position:position+length]
            position = align(position+length)
        elif token == 4: pass
        elif token == 9:
            assert not stack
            return result
        else: raise AssertionError(('FDT token',token))
    raise AssertionError('FDT has no end token')


def value(raw):
    if not raw: return True
    if raw.endswith(b'\0') and all(32 <= n < 127 or n == 0 for n in raw):
        return raw.rstrip(b'\0').decode().split('\0')
    if len(raw) % 4 == 0: return list(struct.unpack('>'+str(len(raw)//4)+'I',raw))
    return raw.hex()


def main():
    sources, cases = {}, []
    files = [DTC_SOURCE/'fdtoverlay.c',DTC_SOURCE/'util.c']+[DTC_SOURCE/'libfdt'/n for n in LIB_FILES]
    headers = list((DTC_SOURCE/'libfdt').glob('*.h'))+[DTC_SOURCE/'util.h']
    with tempfile.TemporaryDirectory(prefix='dijun-dtbo-audit-') as temporary:
        temp = Path(temporary)
        (temp/'version_gen.h').write_text('#define DTC_VERSION "dijun-host-evidence"\n')
        executable = temp/'fdtoverlay'
        subprocess.run(['gcc','-O2','-D_GNU_SOURCE','-I'+str(temp),'-I'+str(DTC_SOURCE/'libfdt'),
                        *map(str,files),'-o',str(executable)],check=True)
        for profile in sorted((ROOT/'dtsrc/O1_asic_dual/profiles').glob('*/profile.json')):
            sample = profile.parent.name
            base = SAMPLES/sample/'analysis/vendor_boot/dtb'
            vendor_boot = SAMPLES/sample/'vendor_boot.img'
            dtbo = SAMPLES/sample/'dtbo.img'
            facts_path = SAMPLES/sample/'analysis/facts.json'
            facts = json.loads(facts_path.read_text())
            sources.update({str(p):sha(p) for p in [base,vendor_boot,dtbo,facts_path]})
            assert sha(dtbo) == facts['headers']['dtbo']['image_sha256']
            assert sha(vendor_boot) == facts['headers']['vendor_boot']['image_sha256']
            _, components = boot_parts(vendor_boot.read_bytes())
            assert components['dtb'] == base.read_bytes(), 'base DTB differs from verified vendor_boot'
            blob = dtbo.read_bytes()
            magic,total,head,esize,count,entries,page,version = struct.unpack_from('>8I',blob)
            assert magic == 0xd7b7ab1e and total <= len(blob) and head == 32 and esize == 32
            assert count == 8 and version == 0
            for i in range(count):
                size,offset,ident,rev,*custom = struct.unpack_from('>8I',blob,entries+i*esize)
                assert offset+size <= total
                overlay = temp/'overlay.dtb'
                overlay.write_bytes(blob[offset:offset+size])
                overlay_tree = nodes(overlay.read_bytes())
                merged = temp/'merged.dtb'
                subprocess.run([str(executable),'-i',str(base),'-o',str(merged),str(overlay)],check=True,capture_output=True)
                tree = nodes(merged.read_bytes())
                haptics = {}
                for path,properties in tree.items():
                    if not path.endswith('/cs40l26@43'): continue
                    status = properties.get('status',b'okay\0')
                    parent = path.rsplit('/',1)[0]
                    active = status in (b'okay\0',b'ok\0') and tree[parent].get('status',b'okay\0') in (b'okay\0',b'ok\0')
                    haptics[path] = dict(active=active,properties={k:value(v) for k,v in properties.items()},
                                         parent_status=value(tree[parent].get('status',b'okay\0')),
                                         driver_fw_defer='cirrus,fw-defer' in properties,
                                         hash_prefixed_fw_defer='#cirrus,fw-defer' in properties,
                                         rom_only='cirrus,rom-only' in properties)
                active = [p for p,info in haptics.items() if info['active']]
                assert len(active) <= 1
                if i == 5:
                    assert value(overlay_tree['/']['board_id']) == [0x90f0000]
                    assert active == ['/soc/i2c@EC100000/cs40l26@43']
                    info = haptics[active[0]]
                    assert tree[active[0]]['bind-product'] == b'dijun\0'
                    assert info['properties']['cirrus,f0-default'] == [130 << 14]
                    assert not info['driver_fw_defer'] and not info['rom_only']
                cases.append(dict(sample=sample,case=f'overlay-{i}',status='PASS',entry=dict(id=ident,rev=rev,custom=custom),
                                  overlay_sha256=sha(overlay),merged_sha256=sha(merged),haptics=haptics,
                                  overlay_identity={k:value(v) for k,v in overlay_tree['/'].items()},
                                  board_identity={k:value(v) for k,v in tree['/'].items() if k in ['model','compatible','board-id','board_id','hwid']},
                                  dijun_properties={path:{k:value(v) for k,v in props.items() if b'dijun' in v}
                                                    for path,props in tree.items() if any(b'dijun' in v for v in props.values())}))
            print('PASS',sample,'8 overlays',flush=True)
    report = dict(status='PASS',grade='S0/S1',scope=__doc__.strip(),cases=cases,sources=sources,
                  tests={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'scripts/firmware_facts.py']},
                  libfdt_sources={str(p):sha(p) for p in files+headers})
    (ROOT/'logs/haptics-devicetree-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(cases),'overlay applications')


if __name__ == '__main__': main()
