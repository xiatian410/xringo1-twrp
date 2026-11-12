#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <map>
#include <pthread.h>
#include <string>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>
#include "infomanager.hpp"
#include <partitions.hpp>
#include <set_metadata.h>
#include <twcommon.h>
#include <variables.h>
namespace fs = std::filesystem;
// FILE_VERSION
static std::string fault;
extern "C" {
size_t __real_fwrite(const void*,size_t,size_t,FILE*);
int __real_fflush(FILE*);
int __real_fclose(FILE*);
int __real_fsync(int);
int __real_rename(const char*,const char*);
int __real_mkstemp(char*);
size_t __wrap_fwrite(const void* p,size_t size,size_t count,FILE* f) {
 if(fault=="no-space"){errno=ENOSPC;return 0;}
 if(fault=="short-write")return __real_fwrite(p,size,count/2,f);
 return __real_fwrite(p,size,count,f);
}
int __wrap_fflush(FILE* f){if(fault=="flush-error"){errno=ENOSPC;return EOF;}return __real_fflush(f);}
int __wrap_fclose(FILE* f){int r=__real_fclose(f);if(fault=="close-error"){errno=EIO;return EOF;}return r;}
int __wrap_fsync(int fd){
 struct stat s;assert(fstat(fd,&s)==0);
 if((fault=="sync-error" && S_ISREG(s.st_mode)) ||
    (fault=="directory-sync-error" && S_ISDIR(s.st_mode))){errno=EIO;return -1;}
 return __real_fsync(fd);
}
int __wrap_rename(const char* a,const char* b){
 if(fault=="interrupted-before-commit")_exit(42);
 if(fault=="rename-error"){errno=EIO;return -1;}
 return __real_rename(a,b);
}
int __wrap_mkstemp(char* p){if(fault=="create-error"){errno=EROFS;return -1;}return __real_mkstemp(p);}
}
namespace android::base {
inline std::map<std::string,std::string> properties;
std::string GetProperty(const std::string& k,const std::string& d){return properties.count(k)?properties.at(k):d;}
bool SetProperty(const std::string& k,const std::string& v){properties[k]=v;return true;}
}
static std::string kBackingFile;
class DataManager {
 public:
 inline static InfoManager persist_;
 inline static bool initialized_=true;
 inline static pthread_mutex_t values_lock_=PTHREAD_MUTEX_INITIALIZER;
 static void SetDefaultValues(){}
 static int GetValue(const std::string& k,std::string& v){return persist_.GetValue(k,v);}
 static int SetValue(const std::string& k,const std::string& v){return persist_.SetValue(k,v);}
 static std::string GetStrValue(const std::string& k){return persist_.GetStrValue(k);}
 static std::string GetCurrentStoragePath(){return "/fixture-storage";}
 static void SetBackupFolder(){}
 static int LoadValues(const std::string&);
 static int SaveValues();
 static int Flush();
 static void UpdateTimezoneEnvironment();
};
// PRODUCTION_METHODS

static const fs::path file=fs::path(TW_PERSIST_DIR)/TW_SETTINGS_FILE;
std::string read_file(){std::ifstream f(file,std::ios::binary);assert(f);return {std::istreambuf_iterator<char>(f),{}};}
void write_file(const std::string& s){std::ofstream f(file,std::ios::binary);f.write(s.data(),s.size());assert(f);}
InfoManager manager(){InfoManager m(file);m.SetFileVersion(FILE_VERSION);return m;}
std::string seed(){auto m=manager();m["keep"]="old";assert(m.SaveValues()==0);return read_file();}
void append_field(std::string& s,const std::string& v){unsigned short len=v.size()+1;s.append((const char*)&len,sizeof(len));s+=v;s+='\0';}
std::string header(){int v=FILE_VERSION;return std::string((const char*)&v,sizeof(v));}
void assert_no_temporary(){for(const auto& p:fs::directory_iterator(TW_PERSIST_DIR))assert(p.path()==file);}
void timezone_seed(const char* zone,const char* selection,int offset=0,int dst=0,int migrated=0){
 auto m=manager();m[TW_TIME_ZONE_VAR]=zone;m[TW_TIME_ZONE_GUISEL]=selection;
 m[TW_TIME_ZONE_GUIOFFSET]=offset;m[TW_TIME_ZONE_GUIDST]=dst;m["tw_device_timezone_migrated"]=migrated;
 assert(m.SaveValues()==0);DataManager::persist_.Clear();assert(DataManager::LoadValues(file)==0);
}
std::string local(int year,int month,int day,int hour){
 std::tm t{};t.tm_year=year-1900;t.tm_mon=month-1;t.tm_mday=day;t.tm_hour=hour;
 t.tm_min=9;t.tm_sec=53;time_t when=timegm(&t);std::tm out{};assert(localtime_r(&when,&out));
 char s[80];assert(strftime(s,sizeof(s),"%Y-%m-%d %H:%M:%S %z",&out));return s;
}
int main(int argc,char** argv){
 assert(argc==2);std::string test=argv[1];
 for(const auto& p:fs::directory_iterator(TW_PERSIST_DIR))fs::remove_all(p.path());
 if(test=="roundtrip"){
  auto m=manager();m["keep"]="first";m["中文"]="value";m["empty"]="";m["int"]=42;
  assert(m.SaveValues()==0);auto n=manager();n["default"]="preserved";assert(n.LoadValues()==0);
  assert(n.GetStrValue("keep")=="first" && n.GetStrValue("中文")=="value");
  assert(n.GetIntValue("int")==42 && n.GetStrValue("default")=="preserved");
  m["keep"]="second";assert(m.SaveValues()==0);assert(n.LoadValues()==0);assert(n.GetStrValue("keep")=="second");
  struct stat st;assert(stat(file.c_str(),&st)==0 && (st.st_mode & 0777)==0664);assert_no_temporary();
 }else if(test=="malformed"){
  auto old=seed();auto base=header();append_field(base,"keep");append_field(base,"new");
  std::vector<std::string> broken={"",header().substr(0,3),base+"x",base+std::string("\0\0",2)};
  auto orphan=base;append_field(orphan,"orphan");broken.push_back(orphan);
  auto nonul=base;nonul.back()='x';broken.push_back(nonul);
  auto embedded=header();append_field(embedded,"keep");append_field(embedded,std::string("a\0b",3));broken.push_back(embedded);
  auto zero=header();append_field(zero,"");append_field(zero,"value");broken.push_back(zero);
  auto huge=base;huge+=std::string("\xff\xff",2);broken.push_back(huge);
  auto negative=header();append_field(negative,"1bad");append_field(negative,"value");broken.push_back(negative);
  for(const auto& b:broken){write_file(old);auto m=manager();assert(m.LoadValues()==0);
    write_file(b);assert(m.LoadValues()!=0);assert(m.GetStrValue("keep")=="old");}
 }else if(test=="limits"){
  auto old=seed();auto m=manager();m["limit"]=std::string(510,'x');assert(m.SaveValues()==0);
  auto n=manager();assert(n.LoadValues()==0 && n.GetStrValue("limit").size()==510);
  old=read_file();for(auto v:{std::string(511,'x'),std::string(65536,'x'),std::string("a\0b",3)}){
    m["limit"]=v;assert(m.SaveValues()!=0);assert(read_file()==old);}
  m.Clear();m[std::string(511,'k')]="x";assert(m.SaveValues()!=0 && read_file()==old);
  m.Clear();m[std::string("k\0x",3)]="x";assert(m.SaveValues()!=0 && read_file()==old);assert_no_temporary();
 }else if(test=="version"){
  seed();auto m=manager();m.SetFileVersion(FILE_VERSION+1);m["keep"]="default";
  assert(m.LoadValues()==0 && m.GetStrValue("keep")=="default");
  InfoManager raw(file);raw["raw"]="yes";assert(raw.SaveValues()==0);InfoManager other(file);
  assert(other.LoadValues()==0 && other.GetStrValue("raw")=="yes");
 }else if(test=="missing-parent"){
  auto old=seed();InfoManager m(file.parent_path()/"missing"/"settings");m["x"]="y";
  assert(m.SaveValues()!=0 && read_file()==old);
 }else if(test=="mount-failure"){
  auto old=seed();PartitionManager.mounted=false;PartitionManager.can_mount=false;
  auto m=manager();m["keep"]="new";assert(m.SaveValues()!=0 && read_file()==old);
  assert(m.LoadValues()!=0 && m.GetStrValue("keep")=="new");
  PartitionManager.can_mount=true;assert(m.SaveValues()==0 && PartitionManager.mounted);
  assert(m.LoadValues()==0 && m.GetStrValue("keep")=="new");
 }else if(test=="backup-without-persist"){
  PartitionManager.mounted=false;PartitionManager.can_mount=false;
  fs::path backup=file.parent_path().parent_path()/"backup.info";
  InfoManager m(backup);m["backup_size"]=123;assert(m.SaveValues()==0);
  InfoManager n(backup);assert(n.LoadValues()==0 && n.GetIntValue("backup_size")==123);
  assert(!PartitionManager.mounted);fs::remove(backup);
 }else if(test=="manager-failure"){
  auto old=seed();assert(DataManager::LoadValues(file)==0);DataManager::persist_["keep"]="new";
  fault="no-space";int r=DataManager::Flush();fault.clear();assert(r!=0);assert(read_file()==old);
  assert(DataManager::Flush()==0);auto m=manager();assert(m.LoadValues()==0 && m.GetStrValue("keep")=="new");
  assert(pthread_mutex_trylock(&DataManager::values_lock_)==0);pthread_mutex_unlock(&DataManager::values_lock_);
 }else if(test.starts_with("timezone-")){
  android::base::properties["ro.twrp.default_timezone"]="CST-8";
  android::base::properties["ro.twrp.default_timezone_selection"]="TAIST-8;TAIDT";
  if(test=="timezone-no-device-default")android::base::properties.clear();
  if(test=="timezone-migration" || test=="timezone-no-device-default"){
   timezone_seed("CST6CDT,M3.2.0,M11.1.0","CST6;CDT,M3.2.0,M11.1.0");
   const bool migrate=test=="timezone-migration";
   assert(DataManager::GetStrValue(TW_TIME_ZONE_VAR)==(migrate?"CST-8":"CST6CDT,M3.2.0,M11.1.0"));
   assert(DataManager::persist_.GetIntValue("tw_device_timezone_migrated")==int(migrate));
   DataManager::UpdateTimezoneEnvironment();
   assert(local(2026,11,10,18)==(migrate?"2026-11-11 02:09:53 +0800":"2026-11-10 12:09:53 -0600"));
   assert(android::base::properties.at("persist.sys.timezone")==DataManager::GetStrValue(TW_TIME_ZONE_VAR));
   assert(DataManager::Flush()==0);DataManager::persist_.Clear();assert(DataManager::LoadValues(file)==0);
   assert(DataManager::GetStrValue(TW_TIME_ZONE_VAR)==(migrate?"CST-8":"CST6CDT,M3.2.0,M11.1.0"));
  }else if(test=="timezone-custom"){
   for(int option=0;option<4;++option){
    timezone_seed(option==0?"IST-5:30":"CST6CDT,M3.2.0,M11.1.0",
                  option==0?"IST-5:30;IDT":"CST6;CDT,M3.2.0,M11.1.0",
                  option==1?30:0,option==2?1:0,option==3?1:0);
    std::string expected=option==0?"IST-5:30":"CST6CDT,M3.2.0,M11.1.0";
    assert(DataManager::GetStrValue(TW_TIME_ZONE_VAR)==expected);assert(DataManager::Flush()==0);
    DataManager::persist_.Clear();assert(DataManager::LoadValues(file)==0);
    assert(DataManager::GetStrValue(TW_TIME_ZONE_VAR)==expected);
   }
  }else{
   timezone_seed("EST5EDT,M3.2.0,M11.1.0","EST5;EDT,M3.2.0,M11.1.0",0,1);
   DataManager::UpdateTimezoneEnvironment();assert(local(2026,1,10,18)=="2026-01-10 13:09:53 -0500");
   assert(local(2026,7,10,18)=="2026-07-10 14:09:53 -0400");
   timezone_seed("CST-8","TAIST-8;TAIDT");DataManager::UpdateTimezoneEnvironment();
   assert(local(2026,1,10,18)=="2026-01-11 02:09:53 +0800");
   assert(local(2026,7,10,18)=="2026-07-11 02:09:53 +0800");
  }
 }else{
  auto old=seed();auto m=manager();m["keep"]="new";
  if(test=="interrupted-before-commit"){
   pid_t child=fork();assert(child>=0);if(child==0){fault=test;m.SaveValues();_exit(1);}
   int s;assert(waitpid(child,&s,0)==child);assert(WIFEXITED(s) && WEXITSTATUS(s)==42);assert(read_file()==old);
  }else{
   fault=test;int r=m.SaveValues();fault.clear();assert(r!=0);
   if(test=="directory-sync-error"){
    auto n=manager();assert(n.LoadValues()==0 && n.GetStrValue("keep")=="new");
   }else assert(read_file()==old);
   assert_no_temporary();
  }
 }
 std::puts("ok");
}
