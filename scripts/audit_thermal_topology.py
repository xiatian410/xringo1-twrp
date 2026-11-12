#!/usr/bin/env python3
"""Resolve six stock dijun CPU thermal-zone identities; no sysfs numbering claim.

Rebuild libfdt and merge original dijun overlay5. Original sensor module match
and registration functions are disassembled only; no kernel probe, sensor,
thermal core numbering or GUI executes.
"""
import json,struct,subprocess,tempfile
from pathlib import Path
from audit_haptics_devicetree import ROOT,DTC_SOURCE,LIB_FILES,nodes,value,sha

def cells(raw):
 assert len(raw)%4==0;return list(struct.unpack('>'+str(len(raw)//4)+'I',raw))
def main():
 priorpath=ROOT/'logs/haptics-devicetree-audit.json';prior=json.loads(priorpath.read_text());sources={str(priorpath.relative_to(ROOT)):sha(priorpath)};cases=[]
 files=[DTC_SOURCE/'fdtoverlay.c',DTC_SOURCE/'util.c']+[DTC_SOURCE/'libfdt'/n for n in LIB_FILES]
 for p in files+list((DTC_SOURCE/'libfdt').glob('*.h'))+[DTC_SOURCE/'util.h']:sources[str(p)]=sha(p)
 with tempfile.TemporaryDirectory(prefix='dijun-thermal-') as tmp:
  tmp=Path(tmp);(tmp/'version_gen.h').write_text('#define DTC_VERSION "dijun-host-evidence"\n');exe=tmp/'merge'
  subprocess.run(['gcc','-O2','-D_GNU_SOURCE','-I'+str(tmp),'-I'+str(DTC_SOURCE/'libfdt'),*map(str,files),'-o',str(exe)],check=True)
  for profile in sorted((ROOT/'dtsrc/O1_asic_dual/profiles').glob('*/profile.json')):
   sample=profile.parent.name;base=ROOT/'firmware/samples'/sample;dtb=base/'analysis/vendor_boot/dtb';dtbo=base/'dtbo.img';blob=dtbo.read_bytes();h=struct.unpack_from('>8I',blob);size,offset,*_=struct.unpack_from('>8I',blob,h[5]+5*h[3]);(tmp/'overlay').write_bytes(blob[offset:offset+size])
   subprocess.run([str(exe),'-i',str(dtb),'-o',str(tmp/'merged'),str(tmp/'overlay')],check=True,capture_output=True)
   expected=next(c for c in prior['cases'] if c['sample']==sample and c['case']=='overlay-5')['merged_sha256'];assert sha(tmp/'merged')==expected
   tree=nodes((tmp/'merged').read_bytes());ph={cells(p['phandle'])[0]:n for n,p in tree.items() if 'phandle' in p};zones=[]
   for name,props in tree.items():
    if not name.startswith('/thermal-zones/') or 'thermal-sensors' not in props:continue
    ref=cells(props['thermal-sensors']);sensor=ph[ref[0]];sp=tree[sensor];assert cells(sp['#thermal-sensor-cells'])==[1] and len(ref)==2
    zones.append(dict(path=name,zone_status=value(props.get('status',b'okay\0')),sensor_path=sensor,sensor_id=ref[1],sensor_status=value(sp.get('status',b'okay\0')),sensor_compatible=value(sp['compatible']),properties={k:value(v) for k,v in props.items() if k not in ['phandle']}))
   cpu,=[z for z in zones if z['path']=='/thermal-zones/cpu-crg'];assert cpu['sensor_id']==0 and cpu['sensor_compatible']==['xring,tsensor'] and cpu['sensor_status']==['okay']
   physical=[z for z in zones if z['sensor_path']==cpu['sensor_path']];assert len(physical)==22 and {z['sensor_id'] for z in physical}==set(range(22))
   modules=list((base/'analysis/vendor_boot').rglob('xring_thermal.ko'));assert len(modules)==1;module=modules[0]
   tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump';disasm=ROOT/'logs'/f'{sample}-thermal-registration.disasm'
   symbols=subprocess.check_output([tool,'-t',str(module)],text=True)
   selected=[n for n in ['xr_soc_tm_probe','xr_virt_tm_probe','__xr_thermal_get_temp','xr_get_thermal_zone_by_id'] if any(line.split()[-1:]==[n] for line in symbols.splitlines())]
   assert set(selected)>={'xr_soc_tm_probe','xr_virt_tm_probe','__xr_thermal_get_temp'}
   disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols='+','.join(selected),str(module)]))
   text=disasm.read_text();registrations=[line.strip() for line in text.splitlines() if 'R_AARCH64_CALL26' in line and ('thermal' in line or 'register' in line)]
   assert registrations
   for p in [dtb,dtbo,module,disasm]:sources[str(p.relative_to(ROOT))]=sha(p)
   assert any('devm_thermal' in call and 'register' in call for call in registrations)
   cases.append(dict(sample=sample,status='PASS',merged_sha256=expected,cpu_zone=cpu,physical_sensor_count=len(physical),zones=zones,registration_calls=registrations,inspected_symbols=selected,module=str(module.relative_to(ROOT)),sysfs_zone_number=None))
   print(sample,'cpu-crg sensor0;22 physical sensors; sysfs ordinal unverified',flush=True)
 config=ROOT/'dtsrc/O1_asic_dual/BoardConfig.mk';props=ROOT/'dtsrc/O1_asic_dual/system.prop';backend=Path('/root/AAA/twrp/bootable/recovery/gui2/backend/status_backend.h');sources[str(config.relative_to(ROOT))]=sha(config);sources[str(props.relative_to(ROOT))]=sha(props);sources[str(backend)]=sha(backend)
 assert 'TW_CUSTOM_CPU_TEMP_PATH :=' not in config.read_text()
 assert 'ro.twrp.cpu_temp_type=cpu-crg' in props.read_text().splitlines()
 assert 'cpu_temperature_valid' in backend.read_text()
 out=dict(status='PASS',scope=__doc__,cases=cases,sources=sources,tests={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__)),'scripts/audit_haptics_devicetree.py':sha(ROOT/'scripts/audit_haptics_devicetree.py')},conclusion='Stock cpu-crg is tsensor hardware channel0 across six matching overlays. This channel index does not establish Linux thermal_zone0 sysfs identity. Maintained configuration selects cpu-crg type, tested separately; GUI temperature field is implemented and tested separately; physical measurements remain unverified.')
 (ROOT/'logs/thermal-topology.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS',len(cases),'stock identities; runtime numbering/GUI/sensor unverified')
if __name__=='__main__':main()
