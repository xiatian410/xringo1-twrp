#!/usr/bin/env python3
"""Prefetch pinned OTA ranges concurrently, then use the verified partition extractor.

Cache files are untrusted inputs: the normal extractor still verifies operation
hashes and full partition hashes. No devices or target executables are used.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,threading,zipfile
from pathlib import Path
from acquire_firmware import ROOT,SAMPLES,CHUNK,HttpRangeFile,sources,parse_manifest,payload_position,extract_partition,sha256_file
NAMES=['boot','init_boot','vendor_boot','recovery','dtbo','vendor_dlkm','system_dlkm','odm_dlkm','vendor','odm','system','system_ext','product','mi_ext','mi_product']
def main():
 tool_digest=sha256_file(__file__)
 sample='os4-stable';base=SAMPLES/sample;report_path=base/'inventory.json';report=json.loads(report_path.read_text());url=sources()[sample]
 cache=base/'range-cache';cache.mkdir(exist_ok=True)
 pin={'url':url,'etag':report['etag'],'size':report['zip_size'],'chunk':CHUNK};pinfile=cache/'pin.json'
 if pinfile.exists():assert json.loads(pinfile.read_text())==pin
 else:pinfile.write_text(json.dumps(pin,indent=2)+'\n')
 manifest=parse_manifest((base/'payload-manifest.pb').read_bytes());start=report['payload_data_zip_offset'];local=threading.local()
 def connection():
  if not hasattr(local,'f'):
   local.f=HttpRangeFile(url);assert local.f.etag==pin['etag'] and local.f.length==pin['size']
  return local.f
 def get(offset):
  path=cache/str(offset);size=min(CHUNK,pin['size']-offset)
  if path.exists() and path.stat().st_size==size:return offset
  data=connection()._chunk(offset);assert len(data)==size
  partial=path.with_suffix('.partial');partial.write_bytes(data);partial.replace(path);return offset
 needed=set()
 pending=[]
 for name in NAMES:
  part=manifest['partitions'][name];out=base/(name+'.img')
  if out.is_file() and out.stat().st_size==part['size'] and sha256_file(out)==part['sha256']:
   report['extracted'][name]=dict(sha256=part['sha256'],size=part['size'],verified=True);continue
  pending.append(name)
  for op in part['operations']:
   if op.get(3,0):needed.update(range((start+op[2])//CHUNK*CHUNK,((start+op[2]+op[3]-1)//CHUNK+1)*CHUNK,CHUNK))
 print('Prefetch',len(needed),'ranges for',pending,flush=True)
 class Cached(HttpRangeFile):
  def _chunk(self,offset):
   p=cache/str(offset)
   return p.read_bytes() if p.is_file() and p.stat().st_size==min(CHUNK,self.length-offset) else super()._chunk(offset)
 def extract_ready(name):
  f=Cached(url)
  try:
   assert f.etag==pin['etag'] and f.length==pin['size']
   with zipfile.ZipFile(f) as z:
    info=z.getinfo('payload.bin');position=payload_position(f,info)
   result=extract_partition(f,start,position+info.file_size,manifest['block_size'],manifest['partitions'][name],base/(name+'.img'))
   print('Verified',name,flush=True);return result
  finally:f.close()
 def ranges(name):
  return {offset for op in manifest['partitions'][name]['operations'] if op.get(3,0) for offset in range((start+op[2])//CHUNK*CHUNK,((start+op[2]+op[3]-1)//CHUNK+1)*CHUNK,CHUNK)}
 bypart={n:ranges(n) for n in pending};finished=set();extracting={}
 # Prioritize the identity/HAL partitions so analysis can begin before product.
 priority={n:i for i,n in enumerate(['vendor','odm','system','system_ext','mi_ext','mi_product','product'])}
 order=sorted(needed,key=lambda x:(min(priority.get(n,0) for n in pending if x in bypart[n]),x))
 with ThreadPoolExecutor(max_workers=16) as pool,ThreadPoolExecutor(max_workers=2) as readers:
  futures={pool.submit(get,x):x for x in order}
  for i,future in enumerate(as_completed(futures),1):
   finished.add(future.result())
   if i%25==0:print('Ranges',i,'/',len(needed),flush=True)
   for name in pending:
    if name not in extracting and bypart[name]<=finished:extracting[name]=readers.submit(extract_ready,name)
  for name,future in extracting.items():report['extracted'][name]=future.result()
 report['parallel_range_cache']=dict(chunks=len(needed),workers=16,tool_sha256=tool_digest,pin=pin)
 report_path.write_text(json.dumps(report,indent=2)+'\n')
 inventory={p.parent.name:json.loads(p.read_text()) for p in sorted(SAMPLES.glob('*/inventory.json'))}
 (ROOT/'firmware-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
 print('All partitions verified',flush=True)
if __name__=='__main__':main()
