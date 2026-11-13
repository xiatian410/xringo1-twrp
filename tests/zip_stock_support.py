"""Original OS4 stable ZIP through host installer/signature/A-B command chain.

Delivered otacerts is used unchanged. A separate package-certificate run is
explicitly diagnostic, not a production trust change. The engine child only
checks argv/ZIP bytes and reports success; it performs no payload operations.
Mounts, properties, GUI and engine are boundaries, not complete OTA proof.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from firmware_facts import boot_parts, ramdisk_entries


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(8*1024*1024),b''):h.update(data)
    return h.hexdigest()


class Stock:
    names=['stock-current-trust','stock-package-cert-diagnostic','stock-ab-dispatch','stock-device-mismatch']

    def __init__(self, work):
        self.work=work
        self.index=json.loads((ROOT/'simulation-report.json').read_text())
        self.image=Path(self.index['image'])
        assert sha(self.image)==self.index['image_sha256']
        self.source=ROOT/'firmware/samples/os4-stable/original-ota.zip'
        self.reference=json.loads((ROOT/'logs/ota-stock-stable-payload.json').read_text())
        self.source_hash=sha(self.source)
        assert self.source_hash==self.reference['source_sha256']
        entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(self.image.read_bytes())[1]['ramdisk'])}
        self.certs=entries['system/etc/security/otacerts.zip']
        with zipfile.ZipFile(self.source) as z:
            self.properties=z.read('payload_properties.txt')
            self.package_cert=z.read('META-INF/com/android/otacert')
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('diagnostic.x509.pem',self.package_cert)
        self.diagnostic_certs=b.getvalue()

    def fixture(self, text):
        text=text.replace('#include <android-base/file.h>','#include <android-base/file.h>\n#include <android-base/parseint.h>\n#include <android-base/stringprintf.h>\n#include <inttypes.h>\n#include <sys/mount.h>\n#define __unused __attribute__((unused))\n#include <fstream>\n#include "twinstall/package.h"')
        text=text.replace('#define TW_AUTO_DISABLE_AVB2_VAR "disable_avb"','#define TW_AUTO_DISABLE_AVB2_VAR "disable_avb"\n#define TW_AUTO_REFLASHTWRP_VAR "reflash"\n#define PROPERTY_VALUE_MAX 92')
        text=text.replace('static string scenario;','''static string scenario;
static unsigned engine_calls=0,mount_calls=0,unmount_calls=0;
static constexpr const char* AB_OTA_PAYLOAD_PROPERTIES="payload_properties.txt";
static constexpr const char* AB_OTA_PAYLOAD="payload.bin";
static constexpr const char* METADATA_PATH="META-INF/com/android/metadata";
namespace android::base {bool GetBoolProperty(const std::string&,bool){return false;}}
struct twrpRepacker {void Flash_Current_Twrp(){assert(false);}};
static int fixture_mount(const char*,const char*,const char*,unsigned long,const void*){++mount_calls;return 0;}
static int fixture_umount(const char*){++unmount_calls;return 0;}
''')
        text=text.replace('value=key=="verify"?', 'value=key=="verify"?')
        a=text.index('    value=key=="verify"?');b=text.index('\n  }',a)
        text=text[:a]+'''    value=key=="verify"?(scenario=="stock-current-trust"||scenario=="stock-package-cert-diagnostic"):0;'''+text[b:]
        text=text.replace('bool UnmountByPath(const string&,bool) {assert(scenario=="unmount-denied");return false;}', '''bool UnmountByPath(const string&,bool) {return true;}
  bool MountByPath(const string&,bool){return true;}
  bool IsMountedByPath(const string&){return false;}
  string GetActiveSlotDisplay(){return "A";}
  void UnlockBlockPartitions(){assert(false);}
  void PrepareAllSuperVolumes(){assert(false);}''')
        text=text.replace('int WaitForChild(pid_t,int*,const string&,bool=true);','int WaitForChild(pid_t,int*,const string&,bool=true);\nint CopyFile(const string&,const string&,int){return 0;}')
        a=text.index('  bool missing=scenario==');b=text.index('  strcpy(value,v.c_str());',a)
        text=text[:a]+'''  map<string,string> props={{"ro.product.device",scenario=="stock-device-mismatch"?"other":"dijun"},{"ro.product.model","25042PN24C"},{"ro.product.name","twrp_dijun"},{"ro.product.cpu.abilist","arm64-v8a"}};
  if(auto i=props.find(name);i!=props.end())v=i->second;
'''+text[b:]
        text=text.replace('int abupdate_binary_command(const char*,int,int,vector<string>*) {assert(false);return INSTALL_ERROR;}','int abupdate_binary_command(const char*,int,int,vector<string>*);')
        marker='// PRODUCTION_METHODS'
        bridge=r'''
static int observed_execve(const char*path,char*const argv[],char*const env[]){
 assert(string(path)=="/system/bin/update_engine_sideload");
 return ::execve("/test",argv,env);
}
#define execve observed_execve
#define mount fixture_mount
#define umount fixture_umount
'''
        text=text.replace(marker,bridge+'\n'+marker+'\n#undef execve\n#undef mount\n#undef umount')
        text=text[:text.index('int main(int argc,char** argv)')]+r'''
static int engine(int argc,char**argv){
 assert(argc==5&&string(argv[0])=="/system/bin/update_engine_sideload");
 assert(string(argv[1])=="--payload=file:///packages/test.zip");
 assert(string(argv[2])=="--offset=5229");
 ifstream prop("/packages/properties",ios::binary);string properties((istreambuf_iterator<char>(prop)),{});
 assert(string(argv[3])=="--headers="+properties);
 assert(string(argv[4]).starts_with("--status_fd="));
 ifstream zip("/packages/test.zip",ios::binary);zip.seekg(5229);char magic[4];zip.read(magic,4);assert(string(magic,4)=="CrAU");
 ofstream("/packages/engine-entered.txt")<<"Original ZIP argv/offset/headers checked; NO payload install\n";
 dprintf(stoi(string(argv[4]).substr(12)),"progress 0.5 1\nset_progress 1\n");return 0;
}
int main(int argc,char**argv){
 if(argc==5)return engine(argc,argv);
 assert(argc==3);scenario=argv[1];bool expected=string(argv[2])=="1";
 int wipe=0;int result=TWinstall_zip("/packages/test.zip",&wipe,false);
 bool entered=fs::exists("/packages/engine-entered.txt");
 printf("stock_result=%d engine_entered=%d mounts=%u unmounts=%u\n",result,entered,mount_calls,unmount_calls);fflush(stdout);
 assert((result==INSTALL_SUCCESS)==expected);assert(entered==expected);
 assert(mount_calls==(expected?1u:scenario=="stock-device-mismatch"?1u:0u));
 int status;errno=0;assert(waitpid(-1,&status,WNOHANG)==-1&&errno==ECHILD);
}
'''
        return text

    def run(self, executable, command, crypto, clang, sources):
        dependencies={str(crypto):sha(crypto),str(clang):sha(clang)}
        for line in subprocess.check_output(['ldd',str(executable)],text=True).splitlines():
            m=re.search(r'(/[^\s()]+)',line)
            if m:dependencies[m[1]]=sha(m[1])
        cases=[]
        for name in self.names:
            jail=self.work/name;jail.mkdir()
            for n in dependencies:
                if n in [str(crypto),str(clang)]:continue
                dest=jail/Path(n).relative_to('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(n,dest);dest.chmod(0o755)
            shutil.copyfile(executable,jail/'test');(jail/'test').chmod(0o755)
            for d in ['packages','tmp','system/bin','system/etc/security']:(jail/d).mkdir(parents=True,exist_ok=True)
            os.link(self.source,jail/'packages/test.zip')
            (jail/'packages/properties').write_bytes(self.properties)
            certs=self.diagnostic_certs if name=='stock-package-cert-diagnostic' else self.certs
            (jail/'system/etc/security/otacerts.zip').write_bytes(certs)
            expected=name in ['stock-package-cert-diagnostic','stock-ab-dispatch']
            run=subprocess.run(['chroot',str(jail),'/test',name,str(int(expected))],capture_output=True,text=True,timeout=180)
            cases.append(dict(name=name,status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,
                expected_install_success=expected,engine_entered=(jail/'packages/engine-entered.txt').exists(),
                trust='package certificate ONLY as diagnostic' if name=='stock-package-cert-diagnostic' else 'unchanged delivered certificates',
                signature_enabled=name in ['stock-current-trust','stock-package-cert-diagnostic'],output=run.stdout+run.stderr))
            print(name,cases[-1]['status'],flush=True)
            if run.returncode:print(cases[-1]['output'][-2500:],flush=True)
        return dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,
            image=str(self.image),image_sha256=sha(self.image),source_zip_sha256=self.source_hash,source_zip_bytes=self.source.stat().st_size,
            delivered_cert_zip_sha256=hashlib.sha256(self.certs).hexdigest(),package_cert_sha256=hashlib.sha256(self.package_cert).hexdigest(),
            cases=cases,sources={str(p):sha(p) for p in [*sources,Path(__file__),ROOT/'scripts/firmware_facts.py',ROOT/'scripts/acquire_firmware.py']},
            binary_dependencies=dependencies,compile_command=command,full_payload_installed=False,production_trust_changed=False)
