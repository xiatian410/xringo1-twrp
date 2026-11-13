"""Host original ZIP installer -> QEMU bridge -> original ARM64 sideload engine.

The child's real argv/status fd are preserved. FileControl/HAL/proc/cleanup
remain explicit fixtures. The expected installation is FAILED at block-readonly
setup, never success. No SnapshotManager, actual mount, slot or device operation.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from zip_stock_support import ROOT, Stock, sha


def run_joined(jail, engine):
    import zip_stock_support
    import zip_install_chain_test
    model=engine.get('finish_model')
    allocated=bool(model and model.get('actual_allocation'))
    prefix='zip-engine-allocated-finish' if allocated else 'zip-engine-model-finish' if model else 'zip-engine-joined'

    class Joined(Stock):
        def fixture(self, text):
            text=super().fixture(text)
            old='return ::execve("/test",argv,env);'
            assert text.count(old)==1
            text=text.replace(old,r'''
 assert(argv[0]&&string(argv[0])==path&&argv[1]&&argv[2]&&argv[3]&&argv[4]&&!argv[5]);
 assert(string(argv[1])=="--payload=file:///packages/test.zip");
 assert(string(argv[2])=="--offset=5229");
 ifstream prop("/packages/properties",ios::binary);string properties((istreambuf_iterator<char>(prop)),{});
 assert(string(argv[3])=="--headers="+properties);
 assert(string(argv[4]).starts_with("--status_fd="));
 ofstream("/packages/engine-entered.txt")<<"Original ZIP parent passed original argv and status fd to ARM64 engine\n";
 vector<string> args={"/qemu","-L","/android","-E","LD_LIBRARY_PATH=/android/system/lib64",
     "/android/system/bin/linker64","/engine"};
 for(unsigned i=1;argv[i];++i)args.emplace_back(argv[i]);
 vector<char*> ptrs;for(auto& a:args)ptrs.push_back(a.data());ptrs.push_back(nullptr);
 return ::execve("/qemu",ptrs.data(),env);''')
            # Observe, never override, the original wait result.
            marker='#define execve observed_execve'
            assert text.count(marker)==1
            text=text.replace(marker,r'''
static pid_t observed_waitpid(pid_t p,int*status,int flags){
 pid_t result=::waitpid(p,status,flags);
 if(result>0)printf("engine_wait_status=%d\n",*status);
 return result;
}
#define waitpid observed_waitpid
'''+marker)
            text=text.replace('#undef execve','#undef execve\n#undef waitpid')
            text=text.replace('assert(entered==expected);','assert(entered);')
            text=text.replace('assert(mount_calls==(expected?1u:scenario=="stock-device-mismatch"?1u:0u));',
                              'assert(mount_calls==1&&unmount_calls==1);')
            text=text.replace('static void SetProgress(float f,bool=false) {',
                              'static void SetProgress(float f,bool=false) {printf("joined_progress=%g\\n",f);')
            text=text.replace('static void ShowProgress(float f,int s) {',
                              'static void ShowProgress(float f,int s) {printf("joined_show=%g,%d\\n",f,s);')
            if model:
                text=text.replace('#include <fstream>','#include <fstream>\n#include <sys/resource.h>')
                text=text.replace('assert(string(path)=="/system/bin/update_engine_sideload");',
                                 'assert(string(path)=="/system/bin/update_engine_sideload");\n struct rlimit lim{256,256};assert(setrlimit(RLIMIT_NOFILE,&lim)==0);')
            return text

        def run(self, executable, command, crypto, clang, sources):
            dependencies={str(crypto):sha(crypto),str(clang):sha(clang)}
            for line in subprocess.check_output(['ldd',str(executable)],text=True).splitlines():
                m=re.search(r'(/[^\s()]+)',line)
                if m:
                    path=Path(m[1]);dependencies[str(path)]=sha(path)
                    dest=jail/path.relative_to('/');dest.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(path,dest);dest.chmod(0o755)
            shutil.copyfile(executable,jail/'test');(jail/'test').chmod(0o755)
            for name in ['packages','tmp','system/bin']:(jail/name).mkdir(parents=True,exist_ok=True)
            os.link(self.source,jail/'packages/test.zip')
            (jail/'packages/properties').write_bytes(self.properties)
            # Use certs already extracted from the delivered image, unchanged.
            assert (jail/'system/etc/security/otacerts.zip').read_bytes()==self.certs
            stdout=ROOT/'logs'/(prefix+'.stdout');stderr=ROOT/'logs'/(prefix+'.stderr')
            with stdout.open('w') as out,stderr.open('w') as err:
                child=subprocess.run(['chroot',str(jail),'/test','stock-current-trust','1' if model else '0'],
                                     stdout=out,stderr=err,timeout=1800)
            output=stdout.read_text();errors=stderr.read_text()
            inventory=ROOT/'firmware/samples/os4-stable/inventory.json'
            partitions=json.loads(inventory.read_text())['partitions']
            rows=re.findall(r'Hash of ([A-Za-z0-9_]+): ([A-F0-9]{64})',errors)
            checks=dict(
                parent_assertions=child.returncode==0,
                whole_zip_signature='whole-file signature verified' in errors,
                bridge_entered=(jail/'packages/engine-entered.txt').is_file(),
                child_exit63='engine_wait_status=16128' in output,
                install_failure='stock_result=1 engine_entered=1 mounts=1 unmounts=1' in output,
                payload_complete='Completed 4933/4933 operations (100%), 7883589123/7883589123 bytes downloaded (100%)' in errors,
                payload_hash='Payload hash matches value in payload.' in errors,
                final_hashes=len(rows)==len(dict(rows))==42 and {n:h.lower() for n,h in rows}=={n:p['sha256'] for n,p in partitions.items()},
                verifier_success='finished FilesystemVerifierAction with code ErrorCode::kSuccess' in errors,
                postinstall_failure='finished last action PostinstallRunnerAction with code ErrorCode::kPostInstallMountError' in errors,
                readonly_boundary='Marking block device /work/system.bin as read_only=1: Inappropriate ioctl for device' in errors,
                mount_not_reached='BOUNDARY denied postinstall mount' not in output,
                pipe_progress=output.count('joined_progress=')>100 and output.count('joined_show=0.375,0')==2,
                no_protocol_error='Invalid updater' not in output and 'Unable to read updater output' not in output,
                cow_views=output.count('BOUNDARY mapped COW view ')==10)
            if model:
                for key in ['child_exit63','install_failure','postinstall_failure','readonly_boundary','mount_not_reached']:
                    del checks[key]
                checks.update(child_exit0='engine_wait_status=0' in output,
                    parent_success='stock_result=0 engine_entered=1 mounts=1 unmounts=1' in output,
                    postinstall_success='finished last action PostinstallRunnerAction with code ErrorCode::kSuccess' in errors,
                    stock_script='boot-complete not detected' in errors,
                    actual_getprop=(jail/'work/getprop-called').is_file() and (jail/'work/getprop-called').read_text()=='dev.bootcomplete',
                    model_mounted='MODEL mount system at /postinstall' in output,
                    model_unmounted='MODEL unmount postinstall' in output,
                    manager_state='MODEL actual FinishedSnapshotWrites result=1 state=2 merges=1' in output,
                    model_slot=(jail/'work/model-active-slot').is_file() and (jail/'work/model-active-slot').read_text()=='1',
                    actual_state_persisted=(jail/'work/meta/state').is_file(),
                    actual_boot_marker=(jail/'work/meta/snapshot-boot').is_file() and (jail/'work/meta/snapshot-boot').read_text()=='_a')
            if allocated:
                checks.update(actual_allocation='MODEL actual controller allocation initialized=10 state=1 seeded=0' in output,
                    no_seeded_allocation='MODEL allocation metadata seeded' not in output,
                    actual_unmapping='MODEL actual snapshot unmapping active=0' in output)
            waits=re.findall(r'engine_wait_status=(\d+)',output)
            engine_exit=os.waitstatus_to_exitcode(int(waits[-1])) if waits else None
            report=dict(status='PASS' if all(checks.values()) else 'FAIL',scope=__doc__,checks=checks,
                image=str(self.image),image_sha256=sha(self.image),source_zip_sha256=self.source_hash,
                source_zip_bytes=self.source.stat().st_size,delivered_cert_zip_sha256=hashlib.sha256(self.certs).hexdigest(),
                sources={str(p):sha(p) for p in [*sources,Path(__file__),ROOT/'tests/zip_stock_support.py',ROOT/'scripts/firmware_facts.py',ROOT/'scripts/acquire_firmware.py']},
                binary_dependencies=dependencies,compile_command=command,engine=engine,
                stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),inventory_sha256=sha(inventory),
                partition_hashes=dict(rows),installation_result='MODEL_SUCCESS' if model and all(checks.values()) else 'FAILED',engine_returncode=engine_exit,
                original_zip_installer_joined=True,signature_enabled=True,full_payload_installed=checks['payload_complete'] and checks['final_hashes'],
                full_ota_install=False,production_trust_changed=False,postinstall_mount_reached=False,
                snapshot_manager_executed=bool(model),slot_switched=False,hardware_testing=False)
            if model:
                report.update(scope=__doc__+'\nModel finish mode: block-readonly/mount/allocation/HAL/slot are explicit models; exact stock script, actual getprop and SnapshotManager state publication run. Model success is NOT full OTA/hardware acceptance.',
                    postinstall_mount_reached=True,postinstall_mount_is_model=True,postinstall_program_executed=True,
                    slot_model_updated=True,physical_slot_switched=False,
                    metadata_state_sha256=sha(jail/'work/meta/state') if (jail/'work/meta/state').is_file() else None)
            if allocated:
                report.update(actual_snapshot_allocation=True,actual_controller_preparation=True,
                    actual_controller_cow_writer=True,allocation_metadata_seeded=False,
                    synthetic_source_layout=True,file_mapping_model=True,
                    scratch_and_daemon_disabled_for_test=True,actual_kernel_mapping=False,
                    scope=__doc__+'\nAllocated model: actual PreparePartitionsForUpdate/SnapshotManager initializes10 COWs, original controller OpenCowWriter and all stock payload operations/hash verification/postinstall/completion execute in one run. Synthetic source LP, independent file DM views, readonly/mount/HAL/slot/proc/cleanup/GUI remain models; scratch/daemon disabled. Not full device OTA.')
            (ROOT/'logs'/(prefix+'.json')).write_text(json.dumps(report,indent=2)+'\n')
            print(report['status'],'ZIP parent -> actual ARM64 engine;',report['installation_result'],'checks',checks,flush=True)
            return report

    original=zip_stock_support.Stock
    argv=sys.argv
    zip_stock_support.Stock=Joined
    sys.argv=['zip_install_chain_test.py','--stock-os4','--report',str(ROOT/'logs'/(prefix+'.json'))]
    try:
        return int(zip_install_chain_test.main())
    finally:
        zip_stock_support.Stock=original
        sys.argv=argv
