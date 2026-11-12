#!/usr/bin/env python3
"""Resolve stock dijun haptic regulator/GPIO phandles across all six profiles.

Original base DTB plus overlay5 are merged with source-built AOSP libfdt.
Relocated original module supplies are read as ELF data; no probe or power is
executed. Init findings cover extracted OS4 init rc files; OS2/OS3 service rc was
not extracted here. Binary services and other runtime writers are not covered. Field VP-dummy warning is observed, not diagnosed.
"""
import json,re,struct,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from audit_haptics_devicetree import ROOT,DTC_SOURCE,LIB_FILES,nodes,value,sha
from haptics_driver_emulation import Module,DEPS
from firmware_facts import haptics_module

NODE='/soc/i2c@EC100000/cs40l26@43'

def one(raw):
 assert len(raw)==4
 return int.from_bytes(raw,'big')

def main():
 priorpath=ROOT/'logs/haptics-devicetree-audit.json';prior=json.loads(priorpath.read_text());sources={str(priorpath.relative_to(ROOT)):sha(priorpath)}
 for group in ['sources','libfdt_sources']:
  for name,digest in prior[group].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name
   assert sha(p)==digest;sources[name]=digest
 cases=[]
 with tempfile.TemporaryDirectory(prefix='dijun-haptic-power-') as tmp:
  temp=Path(tmp);(temp/'version_gen.h').write_text('#define DTC_VERSION "dijun-host-evidence"\n');exe=temp/'merge'
  files=[DTC_SOURCE/'fdtoverlay.c',DTC_SOURCE/'util.c']+[DTC_SOURCE/'libfdt'/n for n in LIB_FILES]
  subprocess.run(['gcc','-O2','-D_GNU_SOURCE','-I'+str(temp),'-I'+str(DTC_SOURCE/'libfdt'),*map(str,files),'-o',str(exe)],check=True)
  for profile in sorted((ROOT/'dtsrc/O1_asic_dual/profiles').glob('*/profile.json')):
   sample=profile.parent.name;base=ROOT/'firmware/samples'/sample;blob=(base/'dtbo.img').read_bytes();header=struct.unpack_from('>8I',blob)
   size,offset,*_=struct.unpack_from('>8I',blob,header[5]+5*header[3]);(temp/'overlay').write_bytes(blob[offset:offset+size])
   subprocess.run([str(exe),'-i',str(base/'analysis/vendor_boot/dtb'),'-o',str(temp/'merged'),str(temp/'overlay')],check=True,capture_output=True)
   expected=next(c for c in prior['cases'] if c['sample']==sample and c['case']=='overlay-5')['merged_sha256'];assert sha(temp/'merged')==expected
   tree=nodes((temp/'merged').read_bytes());ph={one(p['phandle']):n for n,p in tree.items() if 'phandle' in p};assert len(ph)==sum('phandle' in p for p in tree.values())
   node=tree[NODE];assert node['status']==b'okay\0' and node['bind-product']==b'dijun\0'
   supplies={k:ph[one(raw)] for k,raw in node.items() if k.endswith('-supply')}
   assert set(supplies)=={'VA-supply'}
   va=supplies['VA-supply'];vprops=tree[va];assert vprops['regulator-name']==b'mldo8\0'
   upstream=ph[one(vprops['vin-supply'])];uprops=tree[upstream];assert uprops['regulator-name']==b'mbuck10\0' and 'regulator-always-on' in uprops
   assert one(vprops['regulator-min-microvolt'])==1650000 and one(vprops['regulator-max-microvolt'])==1960000
   pins={}
   for key in ['reset-gpios','irq-gpio']:
    cells=list(struct.unpack('>III',node[key]));path=ph[cells[0]];props=tree[path]
    assert one(props['#gpio-cells'])==2 and cells[1]<one(props['xring,nr-gpios'])
    names=props['gpio-line-names'].rstrip(b'\0').decode().split('\0')
    assert len(names)==one(props['xring,nr-gpios'])
    pins[key]=dict(controller=path,offset=cells[1],flags=cells[2],line_name=names[cells[1]])
   assert pins['reset-gpios']['line_name']=='GPIO_105' and pins['reset-gpios']['flags']==1
   assert pins['irq-gpio']['line_name']=='GPIO_046' and pins['irq-gpio']['flags']==0
   irqparent=ph[one(node['interrupt-parent'])];assert irqparent==pins['irq-gpio']['controller']
   assert list(struct.unpack('>II',node['interrupts']))==[14,8]
   pinpath=ph[one(node['pinctrl-0'])];assert pinpath.endswith('/gpio_046_default')
   pindesc={n:{k:value(v) for k,v in p.items()} for n,p in tree.items() if n==pinpath or n.startswith(pinpath+'/')}
   analysis=base/'analysis';facts=json.loads((analysis/'facts.json').read_text());driver=analysis/haptics_module(facts)[0]
   m=Module(driver);symbol=next(s for s in m.symtab.iter_symbols() if s.name=='cs40l26_supplies');assert symbol['st_size']==(48 if sample.startswith('os4-') else 64)
   a=m.symbols['cs40l26_supplies'];names=[m.string(m.u64(a+i*(symbol['st_size']//2))) for i in range(2)];assert names==['VP','VA']
   rc=analysis/'odm/etc/init/vendor.xring.hardware.vibratorfeature.service.rc';commands=[];writes=[]
   if rc.exists():
    for number,line in enumerate(rc.read_text().splitlines(),1):
     text=line.strip()
     if not text or text.startswith('#'):continue
     commands.append(dict(line=number,text=text))
     if text.split()[0]=='write':writes.append(dict(line=number,text=text))
    assert not writes
    sources[str(rc.relative_to(ROOT))]=sha(rc)
   init_matches=[];init_files=[]
   if sample.startswith('os4-'):
    for file in sorted(analysis.rglob('*.rc')):
     if '/init/' not in str(file):continue
     init_files.append(str(file.relative_to(ROOT)));sources[str(file.relative_to(ROOT))]=sha(file)
     for number,line in enumerate(file.read_text(errors='replace').splitlines(),1):
      command=line.strip()
      if command and not command.startswith('#') and re.search(r'cs40l26|0-0043|haptic|vibrat',command,re.I):
       init_matches.append(dict(path=str(file.relative_to(ROOT)),line=number,text=command))
    assert init_files
    initwrites=[c for c in init_matches if c['text'].split()[0]=='write']
    assert [c['text'] for c in initwrites]==['write /sys/class/leds/vibrator/trigger "transient"']
   sources[str(driver.relative_to(ROOT))]=sha(driver)
   cases.append(dict(sample=sample,status='PASS',merged_sha256=expected,module_supplies=names,supply_links=supplies,
    va_regulator=dict(path=va,properties={k:value(v) for k,v in vprops.items()}),
    upstream_regulator=dict(path=upstream,properties={k:value(v) for k,v in uprops.items()}),pins=pins,
    irq_parent=irqparent,irq_cells=[14,8],pinctrl=pindesc,stock_service_rc=str(rc.relative_to(ROOT)) if rc.exists() else None,
    service_commands=commands,service_write_commands=writes,module_supply_struct_size=symbol['st_size'],inspected_init_files=init_files,init_matches=init_matches))
   print('PASS',sample,'VA=mldo8/mbuck10 reset=GPIO_105 IRQ=GPIO_046; VP absent',flush=True)
 field=ROOT/'imgs/built/1/touch-dmesg-before.txt';text=field.read_bytes().decode('utf-16');warnings=[l for l in text.splitlines() if 'supply VP not found' in l and ('0-0043' in l or 'haptic' in l)]
 assert len(warnings)==1;sources[str(field.relative_to(ROOT))]=sha(field)
 tests={str(Path(__file__).resolve().relative_to(ROOT)):sha(Path(__file__)), 'scripts/audit_haptics_devicetree.py':sha(ROOT/'scripts/audit_haptics_devicetree.py'),'scripts/firmware_facts.py':sha(ROOT/'scripts/firmware_facts.py'),'tests/haptics_driver_emulation.py':sha(ROOT/'tests/haptics_driver_emulation.py')}
 report=dict(status='PASS',scope=__doc__,cases=cases,field_VP_warning=warnings[0],sources=sources,tests=tests,
  emulator_files={str(p.relative_to(ROOT)):sha(p) for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name)},
  conclusion='Six stock dijun overlays share VA mldo8/mbuck10, active-low GPIO105 reset and GPIO46 level-low IRQ. Original modules request VP/VA, DT lacks VP. No write command in inspected vibratorfeature rc; absent VP does not justify inventing a supply or establish electrical readiness.')
 (ROOT/'logs/haptics-power-topology.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(cases),'profiles; real voltage/reset/output unknown')
if __name__=='__main__':main()
