#!/usr/bin/env python3
"""Inspect original OS4 dijun overlay-5 touch nodes and resolve phandles.

Rebuild host libfdt overlay tool from bound sources. No bootloader overlay
selection or physical GPIO/regulator/panel behavior is simulated.
"""
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from audit_haptics_devicetree import ROOT, DTC_SOURCE, LIB_FILES, nodes, sha
from firmware_facts import boot_parts


def main():
    prior=json.loads((ROOT/'logs/haptics-devicetree-audit.json').read_text())
    cases,sources=[],{}
    files=[DTC_SOURCE/'fdtoverlay.c',DTC_SOURCE/'util.c']+[DTC_SOURCE/'libfdt'/n for n in LIB_FILES]
    headers=list((DTC_SOURCE/'libfdt').glob('*.h'))+[DTC_SOURCE/'util.h']
    with tempfile.TemporaryDirectory(prefix='dijun-touch-dt-') as temporary:
        temp=Path(temporary);exe=temp/'fdtoverlay'
        (temp/'version_gen.h').write_text('#define DTC_VERSION "dijun-host-evidence"\n')
        subprocess.run(['gcc','-O2','-D_GNU_SOURCE','-I'+str(temp),'-I'+str(DTC_SOURCE/'libfdt'),
                        *map(str,files),'-o',str(exe)],check=True)
        for sample in ['os4-current','os4-stable']:
            root=ROOT/'firmware/samples'/sample
            base=root/'analysis/vendor_boot/dtb';dtbo=root/'dtbo.img'
            original=next(c for c in prior['cases'] if c['sample']==sample and c['case']=='overlay-5')
            for p in [base,dtbo]:
                assert sha(p)==prior['sources'][str(p)]
                sources[str(p)]=sha(p)
            vendor_boot=root/'vendor_boot.img';facts_path=root/'analysis/facts.json'
            facts=json.loads(facts_path.read_text())
            assert sha(vendor_boot)==facts['headers']['vendor_boot']['image_sha256']
            assert sha(dtbo)==facts['headers']['dtbo']['image_sha256']
            assert boot_parts(vendor_boot.read_bytes())[1]['dtb']==base.read_bytes()
            sources.update({str(p):sha(p) for p in [vendor_boot,facts_path]})
            blob=dtbo.read_bytes();entry=struct.unpack_from('>I',blob,20)[0]+5*32
            length,offset=struct.unpack_from('>II',blob,entry)
            overlay=temp/'overlay';merged=temp/'merged'
            overlay.write_bytes(blob[offset:offset+length])
            assert sha(overlay)==original['overlay_sha256']
            subprocess.run([str(exe),'-i',str(base),'-o',str(merged),str(overlay)],check=True,capture_output=True)
            assert sha(merged)==original['merged_sha256']
            tree=nodes(merged.read_bytes())
            by_handle={struct.unpack('>I',p['phandle'])[0]:n for n,p in tree.items() if 'phandle' in p}
            def cells(raw):
                assert len(raw)%4==0
                return list(struct.unpack('>'+str(len(raw)//4)+'I',raw))
            def canonical(props):
                result={}
                for key,raw in props.items():
                    if key=='phandle':continue
                    if key in ['dsi-panel','iovdd-supply','avdd-supply'] or key.startswith('pinctrl-') and key!='pinctrl-names':
                        result[key]=[by_handle[v] for v in cells(raw)]
                    elif key in ['synaptics,irq-gpio','synaptics,reset-gpio']:
                        data=cells(raw);result[key]=[by_handle[data[0]],*data[1:]]
                    else:result[key]=raw.hex()
                return result
            node='/soc/spi@E1507000/synaptics_tcm@0';props=tree[node]
            children=[name for name in tree if name.startswith(node+'/')]
            child_properties={name:{key:raw.hex() for key,raw in tree[name].items()}
                              for name in children}
            assert props['compatible']==b'synaptics,tcm-spi\0'
            assert cells(props['synaptics,panel-display-resolution'])==[1440,3200]
            assert cells(props['synaptics,super-resolution-factor'])==[100]
            assert cells(props['synaptics,irq-gpio'])[1:]==[12,0]
            assert cells(props['synaptics,reset-gpio'])[1:]==[10,0]
            for parent in ['/soc','/soc/spi@E1507000',node,'/soc/xiaomi_touch']:
                assert tree[parent].get('status',b'okay\0') in [b'okay\0',b'ok\0']
            resolved=canonical(props)
            targets={}
            for key in ['dsi-panel','iovdd-supply','avdd-supply','pinctrl-0','pinctrl-1','pinctrl-2','pinctrl-3']:
                for target in resolved[key]:
                    # Pin/regulator/panel nodes may themselves refer to phandles;
                    # preserve exact bytes without claiming semantic equivalence.
                    targets[target]={k:v.hex() for k,v in tree[target].items() if k!='phandle'}
            manifest=ROOT/'dtsrc/O1_asic_dual/profiles'/sample/'runtime-files.list'
            sources[str(manifest)]=sha(manifest)
            firmware={}
            for key in ['synaptics,default-fw-image-name','synaptics,default-thp-config-name']:
                name=props[key].rstrip(b'\0').decode();dest='/lib/firmware/'+name
                matches=[line.split() for line in manifest.read_text().splitlines() if line.split()[2]==dest]
                assert len(matches)==1
                digest=matches[0][0]
                blobpath=ROOT/'dtsrc/O1_asic_dual/prebuilt/common/profile-blobs'/digest
                assert sha(blobpath)==digest
                original_fw=root/'analysis/odm/firmware'/name
                assert sha(original_fw)==digest
                sources.update({str(p):digest for p in [blobpath,original_fw]})
                firmware[dest]=digest
            cases.append(dict(sample=sample,case='original-dijun-touch-overlay-5',status='PASS',
                              touch_child_nodes=children,
                              touch_child_properties=child_properties,
                              merged_sha256=sha(merged),canonical_touch_properties=resolved,
                              resolved_target_properties=targets,firmware=firmware,
                              gpio_active_state=cells(props['synaptics,irq-on-state'])[0]))
            print('PASS',sample,'GPIO/panel/pinctrl/regulator refs resolved; firmware names matched',flush=True)
    assert cases[0]['canonical_touch_properties']==cases[1]['canonical_touch_properties']
    report=dict(status='PASS',scope=__doc__.strip(),cases=cases,
                comparison='All touch node properties equal after resolving direct phandles; target node bytes retained separately.',
                sources=sources,tests={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'scripts/audit_haptics_devicetree.py',ROOT/'scripts/firmware_facts.py']},
                libfdt_sources={str(p):sha(p) for p in files+headers})
    (ROOT/'logs/touch-devicetree-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS 2 original touch overlays; canonical properties identical',flush=True)


if __name__=='__main__':main()
