#!/usr/bin/env python3
"""Execute original BackupTar and exclusion policy across sequential attempts.

Mount/DataManager/users/console and tar boundary are fixtures. Tar boundary
reads actual private host files selected by the original exclusion methods;
no archive/crypto/fork, real unlock, manager, GUI or physical device is executed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from nested_partition_path_test import ROOT, SRC, method

HARNESS = r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>
#include "exclude.hpp"
namespace fs = std::filesystem;
namespace std { template<class... T> string format(const char*,T...){return "data.f2fs.win";} }
#define TW_USE_COMPRESSION_VAR "compression"
#define TW_IS_FBE "fbe"
#define TW_BACKUP_TEXT "backup"
#define LOGERR(...) ((void)0)
struct UsersStruct { int user_id; bool is_decrypted; };
struct { std::vector<UsersStruct> users; auto* GetUsersList(){return &users;} } PartitionManager;
struct DataManager { static int GetIntValue(const char*){return fbe;} static void GetValue(const char*,int& v){v=0;} static void GetValue(const char*,std::string& v){v.clear();} static inline bool fbe=true; };
namespace gui2_console { template<class... T> void info(T...){} template<class... T> void warning(T...){} std::string text(const char* s){return s;} }
namespace TWFunc { template<class... T> void GuiOperationText(T...){} std::string RemoveTrailingSlashes(const std::string&,const bool leave_last=false); }
struct PartitionSettings { std::string backup_folder="output"; };
struct BackupProcess {};
static const std::vector<std::string> bases={"system_ce","misc_ce","vendor_ce","media","user"};
static std::set<std::string> selected;
static bool tar_fail=false;
static unsigned tar_calls=0;
static std::vector<std::string> paths;
struct twrpTar {
 int use_compression=0,use_encryption=0,userdata_encryption=0;
 std::string partition_name,backup_folder;
 PartitionSettings* part_settings=nullptr; TWExclude* backup_exclusions=nullptr;
 void setpassword(std::string){} void setdir(std::string){} void setfn(std::string){} void setsize(unsigned long long){}
 int createTarFork(BackupProcess*) {
  ++tar_calls; selected.clear();
  for(const auto& path:paths){
   bool excluded=false; fs::path p=path;
   while(!p.empty()&&p!="/"){if(backup_exclusions->check_skip_dirs(p.string())){excluded=true;break;}p=p.parent_path();}
   if(!excluded){std::ifstream file("tree"+path);std::string content;file>>content;assert(content==path);selected.insert(path);}
  }
  return tar_fail ? -1 : 0;
 }
};
struct TWPartition {
 TWExclude backup_exclusions;
 bool mounted=true,can_encrypt_backup_=false,use_userdata_encryption_=false,has_data_media_=false;
 std::string mount_point_="/data",backup_display_name_="Data",display_name_="Data",backup_name_="data",current_file_system_="f2fs",backup_file_name_,backup_path_="/data";
 unsigned long long backup_size_=0;
 bool Mount(bool){return mounted;}
 bool BackupTar(PartitionSettings*,BackupProcess*);
};
// METHODS
int main(int argc,char** argv) {
 assert(argc==2); std::string test=argv[1];
 for(int uid:{0,10,11})for(const auto& base:bases){
  auto path="/data/"+base+"/"+std::to_string(uid)+"/file";paths.push_back(path);
  fs::create_directories(fs::path("tree"+path).parent_path());std::ofstream("tree"+path)<<path;
 }
 TWPartition p; PartitionSettings settings;BackupProcess process;
 p.backup_exclusions.add_absolute_dir("/data/user/11"); // explicit base policy survives unlock
 auto check_base=[&]{for(int uid:{0,10,11})for(auto& base:bases)
  assert(p.backup_exclusions.check_skip_dirs("/data/"+base+"/"+std::to_string(uid))==(uid==11&&base=="user"));};
 auto run=[&](bool unlocked10,bool unlocked11,bool fail){
  PartitionManager.users={{0,false},{10,unlocked10},{11,unlocked11}};tar_fail=fail;
  assert(p.BackupTar(&settings,&process)==!fail);
  for(int uid:{0,10,11})for(const auto& base:bases){
   bool wanted=!(uid==11&&base=="user");
   if(p.mount_point_=="/data"&&DataManager::fbe&&uid!=0)wanted&=uid==10?unlocked10:unlocked11;
   assert(selected.contains("/data/"+base+"/"+std::to_string(uid)+"/file")==wanted);
  }
 };
 if(test=="mount-failed") {p.mounted=false;assert(!p.BackupTar(&settings,&process)&&tar_calls==0);check_base();}
 else if(test=="non-data") {p.mount_point_="/cache";run(false,false,false);check_base();}
 else if(test=="non-fbe") {DataManager::fbe=false;run(false,false,false);check_base();}
 else if(test=="locked-base") {run(false,false,false);check_base();}
 else if(test=="unlock-next") {run(false,false,false);run(true,true,false);check_base();}
 else if(test=="failed-retry") {run(false,false,true);run(true,true,false);check_base();}
 else if(test=="relock") {run(true,true,false);run(false,true,false);run(true,true,false);check_base();}
 else if(test=="mixed-users") {run(false,true,false);run(true,false,false);run(true,true,false);check_base();}
 else assert(false);
 std::cout<<"attempts="<<tar_calls<<" current_user_selection=1 base_policy_preserved=1\n";
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=SRC)
    ap.add_argument('--report', type=Path, default=ROOT / 'logs/backup-user-policy.json')
    args = ap.parse_args()
    selections = {args.source / 'partition.cpp': ['bool TWPartition::BackupTar('],
                  SRC / 'exclude.cpp': ['TWExclude::TWExclude()', 'void TWExclude::add_relative_dir(',
                      'void TWExclude::add_absolute_dir(', 'bool TWExclude::check_relative_skip_dirs(',
                      'bool TWExclude::check_absolute_skip_dirs(', 'bool TWExclude::check_skip_dirs('],
                  SRC / 'twrp_functions.cpp': ['std::string TWFunc::RemoveTrailingSlashes(']}
    methods = '\n\n'.join(method(path.read_text(), signature)
                          for path, signatures in selections.items() for signature in signatures)
    cases = []
    with tempfile.TemporaryDirectory(prefix='backup-user-policy-') as tmp:
        work = Path(tmp)
        code = work / 'test.cpp'
        code.write_text(HARNESS.replace('// METHODS', methods))
        cmd = ['g++', '-std=c++23', '-O1', '-g', '-fno-pie', '-no-pie',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I' + str(SRC),
               str(code), '-o', str(work / 'test')]
        subprocess.run(cmd, check=True)
        for name in ['locked-base', 'unlock-next', 'failed-retry', 'relock', 'mixed-users',
                     'mount-failed', 'non-data', 'non-fbe']:
            wd = work / name; wd.mkdir()
            run = subprocess.run([str(work / 'test'), name], cwd=wd, capture_output=True,
                                 text=True, timeout=10)
            cases.append(dict(case=name, status='PASS' if run.returncode == 0 else 'FAIL',
                              returncode=run.returncode, output=run.stdout + run.stderr))
            print(name, cases[-1]['status'], flush=True)
    paths = [*selections, SRC / 'exclude.hpp', Path(__file__), ROOT / 'tests/nested_partition_path_test.py']
    report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',
                  scope=__doc__, cases=cases, compile_command=cmd,
                  sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    return report['status'] != 'PASS'


if __name__ == '__main__':
    raise SystemExit(main())
