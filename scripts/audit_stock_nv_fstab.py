#!/usr/bin/env python3
"""Trace NV declarations to six stock recovery/vendor_boot ramdisks.

Original OTA manifest hashes establish image identity, not actual partition
presence, contents, purpose or appropriateness of exposing a GUI action.
"""
import hashlib
import json
from pathlib import Path
from acquire_firmware import parse_manifest
from firmware_facts import boot_parts,ramdisk_entries

ROOT=Path(__file__).resolve().parents[1]
SAMPLES=['os2-initial','os2-final','os3-initial','os3-final','os4-current','os4-stable']
NAMES=['nvram','proinfo','protect_f','protect_s','nvdata','nvcfg']

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def rows(blob):
    result=[]
    for number,line in enumerate(blob.decode().splitlines(),1):
        if not line.strip() or line.lstrip().startswith('#'):continue
        f=line.split();assert len(f)==5,(number,line)
        if f[0].startswith('/dev/block/by-name/') and f[0].rsplit('/',1)[-1] in NAMES:
            result.append(dict(line=number,source=f[0],mount_point=f[1],filesystem=f[2],options=f[3],flags=f[4]))
    assert len(result)==6
    assert {r['source'].rsplit('/',1)[-1] for r in result}==set(NAMES)
    return result

def main():
    maintained=ROOT/'dtsrc/O1_asic_dual/recovery.fstab'
    current=rows(maintained.read_bytes())
    sources=[Path(__file__).resolve(),ROOT/'scripts/acquire_firmware.py',ROOT/'scripts/firmware_facts.py',maintained]
    cases=[]
    for sample in SAMPLES:
        folder=ROOT/'firmware/samples'/sample
        manifest_path=folder/'payload-manifest.pb'
        manifest=parse_manifest(manifest_path.read_bytes())
        sources.append(manifest_path)
        for kind,name,extracted in [
            ('recovery','system/etc/recovery.fstab','analysis/recovery/ramdisk/system/etc/recovery.fstab'),
            ('vendor_boot','first_stage_ramdisk/fstab.O1_asic','analysis/vendor_boot/fragment-0/first_stage_ramdisk/fstab.O1_asic')]:
            image=folder/(kind+'.img');record=manifest['partitions'][kind]
            assert image.stat().st_size==record['size'] and sha(image)==record['sha256']
            header,parts=boot_parts(image.read_bytes())
            ramdisk=parts['ramdisk'] if kind=='recovery' else parts['fragment-0']
            found=[entry[-1] for entry in ramdisk_entries(ramdisk) if entry[0]==name]
            assert len(found)==1
            extracted_path=folder/extracted
            assert found[0]==extracted_path.read_bytes()
            stock=rows(found[0])
            # Exact field comparison, excluding line number and row order.
            field_names=['source','mount_point','filesystem','options','flags']
            canonical=lambda group:sorted(tuple(row[k] for k in field_names) for row in group)
            assert canonical(stock)==canonical(current)
            sources.extend([image,extracted_path])
            cases.append(dict(sample=sample,kind=kind,status='PASS',image_sha256=record['sha256'],
                              ramdisk_entry=name,fstab_sha256=hashlib.sha256(found[0]).hexdigest(),rows=stock,
                              exact_maintained_field_match=True))
            print(sample,kind,'PASS: six NV entries match maintained fields',flush=True)
    report=dict(status='PASS',scope=__doc__,cases=cases,maintained_rows=current,
                conclusions=['All six samples declare the six named NV/protection partitions in both original ramdisks.',
                             'Their source, mount path, filesystem, options and flags match the maintained NV declarations.',
                             'Declarations alone do not establish runtime presence or user-storage semantics.',
                             'No partition, production code or image was changed.'],
                sources={str(p):sha(p) for p in sources})
    (ROOT/'logs/stock-nv-fstab-audit.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
