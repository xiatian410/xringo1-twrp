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
            for outcome in ['success','failure'] if command!='cmd' else ['failure']:
                for entry in ['direct','startup']:
                    run = subprocess.run([str(p/'test'),command,operation,outcome,entry],cwd=p,capture_output=True,text=True,timeout=5)
                    row = dict(case=f'{command}-{outcome}-{entry}',status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,output=run.stdout+run.stderr)
                    rows.append(row);print(row['status'],row['case'],flush=True)
    sources = [args.source,Path(__file__).resolve(),ROOT/'tests/nested_partition_path_test.py']
    report = dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',scope=__doc__,cases=rows,
                  sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},compile_command=compile_command)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'


if __name__ == '__main__':
    raise SystemExit(main())
