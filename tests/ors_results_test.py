#!/usr/bin/env python3
"""Execute original ORS parser and startup action with private script files.

Partition operations, shell execution, settings, console and reboot are explicit
fixtures. No phone, physical partitions, actual commands or reboot. Checks
failure propagation and stopping before a subsequent command/automatic reboot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import ROOT, SRC, method


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=SRC/'openrecoveryscript.cpp')
    ap.add_argument('--report', type=Path, required=True)
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument('--sequence', action='store_true', help='Test temporary/cache script ordering and failure aggregation')
    modes.add_argument('--staging', action='store_true', help='Test source preservation and failure propagation during script staging')
    modes.add_argument('--arguments', action='store_true', help='Test missing backup options and setting names without crashing')
    args = ap.parse_args()
    text = args.source.read_text()
    production = '\n'.join(method(text, s) for s in ['int OpenRecoveryScript::run_script_file(', 'int OpenRecoveryScript::Run_OpenRecoveryScript_Action('])
    fixture = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cerrno>
#include <string>
#include <vector>
#include <filesystem>
#include <fstream>
#include <unistd.h>
using namespace std;
#define SCRIPT_COMMAND_SIZE 512
#define SCRIPT_FILE_TMP "script.txt"
#define TW_SIMULATE_ACTIONS "simulate"
#define TW_BACKUP_NAME "name"
#define TW_SKIP_DIGEST_CHECK_VAR "digest"
#define TW_BACKUPS_FOLDER_VAR "folder"
#define LOGERR(...) ((void)0)
#define LOGINFO(...) ((void)0)
#define gui_print(...) ((void)0)
enum {SYSTEM,RECOVERY,POWER_OFF,BOOTLOADER,DOWNLOAD,EDL};
static bool succeeds=false;
static int calls=0, tail=0, updates=0, reboots=0, disabled=0,done=0;
static string expected_operation;
static int operation(const string& name){assert(name==expected_operation);++calls;return succeeds?1:0;}
struct DataManager {
 template<class T>static void SetValue(const string& key,const T&){if(key=="sentinel")++tail;if(key=="tw_page_done")++done;}
 template<class T>static void GetValue(const string&,T& out){out=T{};}
};
struct PartitionList {string mount_point;};
struct TWPartitionManager {
 static bool IsBackupNameValid(const string&,bool,bool){return true;}
 string GetAndroidRootPath(){return "/system_root";}
 int WipeByPath(const string& p){return operation("wipe:"+p);}
 int WipeDalvikCache(){return operation("dalvik");}
 int FactoryReset(){return operation("factory");}
 int FormatData(){return operation("format");}
 int MountByPath(const string& p,bool){return operation("mount:"+p);}
 int UnmountByPath(const string& p,bool){return operation("unmount:"+p);}
 void UpdateSystemDetails(){++updates;}
 void MountAllStorage(){}void UnlockBlockPartitions(){}
 void GetPartitionList(const char*,vector<PartitionList>*){}
 bool IsMountedByPath(const string&){return false;}
 void SetRestoreFiles(const string&){}bool RunRestore(const string&){return true;}
 int FixContexts(){return 0;}int DecryptDevice(const string&,int){return 0;}
} PartitionManager;
namespace TWFunc {
 bool IsPathExists(const string& p){return filesystem::exists(p);}
 bool RecursiveMkdir(const string&){return true;}
 int ExecCmd(const string&){operation("cmd");return succeeds?0:-1;}
 void ListMounts(){}void DisableStockRecoveryReplace(){++disabled;}
 int TwReboot(int){++reboots;return 0;}
 vector<string> SplitString(const string&,const string&){return {"fixture"};}
}
namespace gui2_console {
 string text(const string& s){return s;}
 template<class...T>void info(T&&...){}
 template<class...T>void log_error(T&&...){}
}
namespace Device {enum BuiltinAction{REBOOT_BOOTLOADER};}
constexpr int INSTALL_REBOOT=5;
static int twrp_sideload(const char*,Device::BuiltinAction*){return 1;}
static int property_set(const char*,const char*){return 0;}
static int no_sleep(unsigned){return 0;}
#define usleep no_sleep
struct OpenRecoveryScript {
 static int run_script_file();static int Run_OpenRecoveryScript_Action();
 static int check_for_script_file(){return 0;}
 static int Install_Command(const string&){return 0;}
 static int Backup_Command(const string&){return 0;}
 static int remountrw(){return 0;}
};
// PRODUCTION
int main(int argc,char** argv){
 assert(argc==5);string command=argv[1];expected_operation=argv[2];succeeds=string(argv[3])=="success";
 bool startup=string(argv[4])=="startup";
 {ofstream script(SCRIPT_FILE_TMP);script<<command<<"\nset sentinel reached\n";}
 int rc=startup?OpenRecoveryScript::Run_OpenRecoveryScript_Action():OpenRecoveryScript::run_script_file();
 bool missing=command=="cmd";
 assert(calls==(missing?0:1));
 bool expected_success=succeeds&&!missing;
 printf("result=%d calls=%d tail=%d reboots=%d done=%d\n",rc,calls,tail,reboots,done);fflush(stdout);
 assert(rc==(expected_success?0:1));assert(tail==(expected_success?1:0));
 assert(reboots==(startup&&expected_success?1:0));
 assert(disabled==reboots);assert(done==(startup&&!expected_success?1:0));
 assert(updates==(expected_operation=="wipe:/system"&&expected_success?1:0));
 assert(!filesystem::exists(SCRIPT_FILE_TMP));
 puts("ors_result_stops_tail_and_automatic_reboot=1");
}
'''.replace('// PRODUCTION', production)
    if args.sequence:
        fixture = fixture.replace('static bool succeeds=false;', 'static bool succeeds=false; static int first=-1, second=-1, checked=0;')
        fixture = fixture.replace('static int check_for_script_file(){return 0;}', '''static int check_for_script_file(){
 ++checked;if(second<0)return 0;succeeds=second==0;
 filesystem::rename("cache-script.txt",SCRIPT_FILE_TMP);return 1;
}''')
        fixture = fixture[:fixture.index('int main(int argc,char** argv)')] + r'''
int main(int argc,char** argv){
 assert(argc==3);first=atoi(argv[1]);second=atoi(argv[2]);expected_operation="cmd";
 if(second>=0){ofstream cache("cache-script.txt");cache<<"cmd fixture-command\nset sentinel reached\n";}
 if(first>=0){succeeds=first==0;ofstream script(SCRIPT_FILE_TMP);script<<"cmd fixture-command\nset sentinel reached\n";}
 int rc=OpenRecoveryScript::Run_OpenRecoveryScript_Action();
 bool failed=first==1 || (first!=1 && second==1);
 bool ran=first>=0 || (first!=1 && second>=0);
 int expected_calls=(first>=0?1:0)+(first!=1&&second>=0?1:0);
 int expected_tail=(first==0?1:0)+(first!=1&&second==0?1:0);
 bool ok=ran&&!failed;
 printf("result=%d calls=%d tail=%d cache_checks=%d reboots=%d done=%d\n",rc,calls,tail,checked,reboots,done);fflush(stdout);
 assert(rc==(ok?0:1));assert(calls==expected_calls);assert(tail==expected_tail);
 assert(checked==(first==1?0:1));assert(reboots==(ok?1:0));assert(disabled==reboots);assert(done==(ok?0:1));
 assert(!filesystem::exists(SCRIPT_FILE_TMP));
 assert(filesystem::exists("cache-script.txt")==(first==1&&second>=0));
 filesystem::remove("cache-script.txt");
 puts("ors_sequence_failure_preserved=1");
}
'''
    if args.staging:
        extra = '\n'.join(method(text, s) for s in ['int OpenRecoveryScript::check_for_script_file(', 'int OpenRecoveryScript::copy_script_file('])
        copier = method((SRC/'twrp_functions.cpp').read_text(), 'int TWFunc::CopyFile(')
        fixture = fixture.replace('#include <cassert>', '#include <sys/stat.h>\n#include <cassert>')
        fixture = fixture.replace('static bool succeeds=false;', '''namespace fs = std::filesystem;
#define DATA_LOGS_DIR "data-logs"
static bool succeeds=false;
static bool mount_ok=true, chmod_fail=false, unlink_fail=false;
static string source_path;
static int checked_unlink(const char* path){if(unlink_fail&&source_path==path){errno=EACCES;return -1;}return ::unlink(path);}
static int checked_chmod(const char* path,mode_t mode){if(chmod_fail){errno=EIO;return -1;}return ::chmod(path,mode);}
#define unlink checked_unlink
#define chmod checked_chmod
''')
        fixture = fixture.replace('return operation("mount:"+p);', 'return mount_ok;')
        fixture = fixture.replace('namespace TWFunc {', '''namespace TWFunc {
 string GetLogDir(){return "cache";}
 int CopyFile(const string&,const string&,int,bool=true);
''')
        fixture = fixture.replace(' static int check_for_script_file(){return 0;}', ' static int check_for_script_file();static int copy_script_file(string);')
        fixture = fixture[:fixture.index('int main(int argc,char** argv)')] + '\n' + copier + '\n' + extra + r'''
int main(int argc,char** argv){
 assert(argc==3);string entry=argv[1],failure=argv[2];bool cache=entry!="copy";
 source_path=cache?"cache/recovery/openrecoveryscript":"source.txt";
 filesystem::create_directories("cache/recovery");expected_operation="cmd";succeeds=true;
 const string content="cmd fixture-command\nset sentinel reached\n";
 bool absent=failure=="absent",same=failure=="same";
 if(same)source_path=SCRIPT_FILE_TMP;
 if(!absent){ofstream source(source_path);source<<content;}
 if(failure=="open")filesystem::create_directory(SCRIPT_FILE_TMP);
 if(failure=="chmod")chmod_fail=true;
 if(failure=="unlink")unlink_fail=true;
 if(failure=="mount")mount_ok=false;
 bool prior=entry=="action-prior";
 if(prior){ofstream temp(SCRIPT_FILE_TMP);temp<<content;}
 int rc=entry=="copy"?OpenRecoveryScript::copy_script_file(source_path):
        entry=="check"?OpenRecoveryScript::check_for_script_file():OpenRecoveryScript::Run_OpenRecoveryScript_Action();
 bool failed=failure=="open"||failure=="chmod"||failure=="unlink";
 bool success=!failed&&!absent&&failure!="mount";
 printf("entry=%s fault=%s result=%d source=%d staged=%d calls=%d reboots=%d done=%d\n",entry.c_str(),failure.c_str(),rc,(int)filesystem::exists(source_path),(int)filesystem::exists(SCRIPT_FILE_TMP),calls,reboots,done);fflush(stdout);
 if(entry=="copy"||entry=="check"){
  assert(rc==(failed?(cache?-1:0):(success?1:0)));
  assert(calls==0&&reboots==0);
 }else{
  bool ok=success||prior&&!failed;
  assert(rc==(ok?0:1));assert(reboots==(ok?1:0));assert(done==(ok?0:1));assert(calls==(prior?1:0)+(success?1:0));
 }
 if(!absent&&(failed||failure=="mount"||same)){
  assert(filesystem::exists(source_path));ifstream source(source_path);string got((istreambuf_iterator<char>(source)),{});assert(got==content);
 }else if(!absent)assert(!filesystem::exists(source_path));
 if(failed&&failure!="open")assert(!filesystem::exists(SCRIPT_FILE_TMP));
 if(success&&(entry=="copy"||entry=="check")){ifstream stage(SCRIPT_FILE_TMP);string got((istreambuf_iterator<char>(stage)),{});assert(got==content);}
 unlink_fail=false;chmod_fail=false;filesystem::remove_all("cache");filesystem::remove_all(SCRIPT_FILE_TMP);filesystem::remove("source.txt");
 puts("ors_staging_source_preserved=1");
}
'''
    if args.arguments:
        fixture = fixture.replace('#include <cassert>', '#include <type_traits>\n#include <cassert>')
        fixture = fixture.replace('static bool succeeds=false;', 'static string observed_setting, backup_options; static int backup_calls=0; static bool succeeds=false;')
        fixture = fixture.replace('template<class T>static void SetValue(const string& key,const T&){if(key=="sentinel")++tail;if(key=="tw_page_done")++done;}', '''template<class T>static void SetValue(const string& key,const T& value){
 if(key=="sentinel")++tail;if(key=="tw_page_done")++done;
 if constexpr(is_convertible_v<const T&,string>){if(key=="option")observed_setting=string(value);}
}''')
        fixture = fixture.replace('static int Backup_Command(const string&){return 0;}', 'static int Backup_Command(const string& options){++backup_calls;backup_options=options;return 0;}')
        fixture = fixture[:fixture.index('int main(int argc,char** argv)')] + r'''
int main(int argc,char** argv){
 assert(argc==4);string command=argv[1];bool valid=string(argv[2])=="valid",startup=string(argv[3])=="startup";
 {ofstream script(SCRIPT_FILE_TMP);script<<command<<"\nset sentinel reached\n";}
 observed_setting="unchanged";
 int rc=startup?OpenRecoveryScript::Run_OpenRecoveryScript_Action():OpenRecoveryScript::run_script_file();
 printf("result=%d tail=%d reboots=%d done=%d backups=%d\n",rc,tail,reboots,done,backup_calls);fflush(stdout);
 assert(rc==(valid?0:1));assert(tail==(valid?1:0));assert(reboots==(valid&&startup?1:0));assert(disabled==reboots);
 assert(done==(!valid&&startup?1:0));assert(calls==0);assert(!filesystem::exists(SCRIPT_FILE_TMP));
 bool backup=valid&&command.starts_with("backup ");
 assert(backup_calls==(backup?1:0));if(backup)assert(backup_options=="S");
 if(command=="set option value")assert(observed_setting=="value");
 else if(command=="set option")assert(observed_setting.empty());
 else assert(observed_setting=="unchanged");
 puts("ors_missing_argument_rejected_without_crash=1");
}
'''
    rows = []
    commands = [('wipe cache','wipe:/cache'),('wipe /cache','wipe:/cache'),
                ('wipe system','wipe:/system'),('wipe /system_root','wipe:/system'),
                ('wipe dalvik','dalvik'),('wipe data','factory'),('wipe factoryreset','factory'),
                ('format data','format'),('format /data','format'),
                ('mount system','mount:/system_root'),('mount /data','mount:/data'),
                ('unmount system','unmount:/system_root'),('umount /data','unmount:/data'),
                ('cmd fixture-command','cmd'),('cmd','cmd')]
    with tempfile.TemporaryDirectory(prefix='ors-results-') as tmp:
        p = Path(tmp);(p/'test.cpp').write_text(fixture)
        compile_command = ['g++','-std=c++23','-O1','-g','-fsanitize=address,undefined','-fno-pie','-no-pie',str(p/'test.cpp'),'-o',str(p/'test')]
        subprocess.run(compile_command, check=True)
        for command, operation in commands:
            if args.sequence or args.staging or args.arguments:
                break
            for outcome in ['success','failure'] if command!='cmd' else ['failure']:
                for entry in ['direct','startup']:
                    run = subprocess.run([str(p/'test'),command,operation,outcome,entry],cwd=p,capture_output=True,text=True,timeout=5)
                    row = dict(case=f'{command}-{outcome}-{entry}',status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,output=run.stdout+run.stderr)
                    rows.append(row);print(row['status'],row['case'],flush=True)
        if args.arguments:
            for command in ['backup', 'backup ', 'backup    ', 'set', 'set ', 'set    ', 'backup S', 'backup S label', 'set option', 'set option value']:
                valid = command in ['backup S', 'backup S label', 'set option', 'set option value']
                for entry in ['direct', 'startup']:
                    run = subprocess.run([str(p/'test'), command, 'valid' if valid else 'invalid', entry], cwd=p, capture_output=True, text=True, timeout=5)
                    row = dict(case=f'{command!r}-{entry}', status='PASS' if run.returncode==0 else 'FAIL', returncode=run.returncode, output=run.stdout+run.stderr)
                    rows.append(row);print(row['status'],row['case'],flush=True)
        if args.staging:
            for entry in ['copy','check','action','action-prior']:
                faults = ['success','chmod','unlink','absent']
                faults += ['same','open'] if entry=='copy' else ['mount']
                if entry in ['check','action']:faults+=['open']
                for fault in faults:
                    case_dir = p/f'{entry}-{fault}'
                    case_dir.mkdir()
                    run = subprocess.run([str(p/'test'),entry,fault],cwd=case_dir,capture_output=True,text=True,timeout=5)
                    row = dict(case=f'{entry}-{fault}',status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,output=run.stdout+run.stderr)
                    rows.append(row);print(row['status'],row['case'],flush=True)
        if args.sequence:
            for first in [-1,0,1]:
                for second in [-1,0,1]:
                    run = subprocess.run([str(p/'test'),str(first),str(second)],cwd=p,capture_output=True,text=True,timeout=5)
                    row = dict(case=f'temporary-{first}-cache-{second}',status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,output=run.stdout+run.stderr)
                    rows.append(row);print(row['status'],row['case'],flush=True)
    sources = [args.source,Path(__file__).resolve(),ROOT/'tests/nested_partition_path_test.py']
    if args.staging:sources.append(SRC/'twrp_functions.cpp')
    scope = __doc__ + (' Temporary/cache scripts: absent/success/failure combinations; first failure leaves cache unconsumed, second failure blocks automatic reboot after first success.' if args.sequence else '')
    if args.staging:scope += ' Original check/copy/parser/action and TWFunc::CopyFile with private files; mount/chmod/unlink faults injected; checks source bytes and partial temporary cleanup. No mount, crash durability, concurrent pathname replacement or actual shell/reboot.'
    if args.arguments:scope += ' Missing/space-only backup options and setting names: reject before null strcpy, stop tail and startup automatic reboot; valid backup options and set empty/value controls preserved. Full original parser/action under ASan/UBSan; backup operation is an explicit fixture.'
    report = dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',scope=scope,cases=rows,
                  sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},compile_command=compile_command)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'


if __name__ == '__main__':
    raise SystemExit(main())
