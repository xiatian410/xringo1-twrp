#include <algorithm>
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <format>
#include <fstream>
#include <string>
#include <vector>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <android-base/file.h>
#include <android-base/hex.h>
#include <android-base/strings.h>
#include <android-base/scopeguard.h>
#include "data.hpp"
#include "twrp_digest_driver.hpp"
#include "twrp_functions.hpp"
namespace fs = std::filesystem;
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static std::string scenario, fault, suffix, expected_hex, destination, previous_bytes, archive_path;
static bool previous_exists=false,previous_directory=false,previous_symlink=false;
static int use_sha2=0, staged_fd=-1, parent_fd=-1, creates=0, write_calls=0, file_syncs=0, dir_syncs=0, closes=0, renames=0, successes=0, errors=0, performance=0, backups=0;
static bool cancelled=false;
static std::vector<std::string> operations;
static std::string contents(const fs::path& p) { std::ifstream f(p,std::ios::binary); CHECK(f.good()); return {std::istreambuf_iterator<char>(f),{}}; }
static void put(const fs::path& p,const std::string& s) {std::ofstream f(p,std::ios::binary); f.write(s.data(),s.size());f.close();CHECK(!f.fail());}
static void unchanged_publication() {
 CHECK(fs::exists(destination)==previous_exists);
 CHECK(fs::is_symlink(destination)==previous_symlink);
 if(previous_exists&&!previous_directory)CHECK(contents(destination)==previous_bytes);
}
void DataManager::GetValue(const std::string&,int& v) {v=use_sha2;}
void console_event(const std::string& s) {if(s=="digest_created"){++successes;if(scenario=="caller-cancel-after-digest")cancelled=true;}if(s=="digest_error")++errors;}
int tw_set_default_metadata(const char* p) {operations.push_back("metadata");return chmod(p,0644);}
namespace TWFunc {
std::string GetFilename(const std::string& s) {return fs::path(s).filename().string();}
bool WriteToFile(const std::string& p,const std::string& s) {
 // Original helper body, used only by the pre-fix negative control.
 std::ofstream file(p,std::ios::out|std::ios::trunc);if(!file.is_open())return false;
 file.write(s.data(),static_cast<std::streamsize>(s.size()));file.close();return !file.fail();
}
void SetPerformanceMode(bool on) {performance+=on?1:-1;CHECK(performance>=0);}
}
namespace android::base {
bool ReadFdToString(borrowed_fd fd,std::string* out) {out->clear();char b[4096];ssize_t n;while((n=TEMP_FAILURE_RETRY(read(fd.get(),b,sizeof b)))>0)out->append(b,n);return n==0;}
bool EqualsIgnoreCase(std::string_view a,std::string_view b) {return a.size()==b.size()&&std::equal(a.begin(),a.end(),b.begin(),[](char x,char y){return tolower(x)==tolower(y);});}
std::string HexString(const void* p,size_t n) {std::string s;auto b=static_cast<const unsigned char*>(p);for(size_t i=0;i<n;++i)s+=std::format("{:02x}",b[i]);return s;}
}
struct TWPartition;
struct PartitionSettings {TWPartition* part=nullptr;std::string backup_folder="backup";bool generate_digest=true;int file_time=0,img_time=0;};
enum class BackupMethod {kFiles,kImage};
struct TWPartition {std::string backup_file_name_="data.ext4.win";BackupMethod backup_method_=BackupMethod::kFiles;bool Backup(PartitionSettings*,int*){++backups;return true;}};
struct TWPartitionManager {int backup_process_=0;bool CheckBackupCancel(){return cancelled;}bool BackupPartition(PartitionSettings*);};
// PRODUCTION_BACKUP_PARTITION
extern "C" int __real_open(const char*,int,...);
extern "C" int __real_mkostemp(char*,int);
extern "C" ssize_t __real_write(int,const void*,size_t);
extern "C" int __real_fsync(int);
extern "C" int __real_close(int);
extern "C" int __real_rename(const char*,const char*);
extern "C" int __wrap_open(const char* p,int flags,...) {
 mode_t mode=0;if(flags&O_CREAT){va_list args;va_start(args,flags);mode=va_arg(args,int);va_end(args);}
 if(std::string(p)=="backup"&&(flags&O_DIRECTORY)) {
  operations.push_back("directory-open");if(fault=="dir-open"){errno=EACCES;return -1;}
  parent_fd=__real_open(p,flags,mode);return parent_fd;
 }
 return __real_open(p,flags,mode);
}
extern "C" int __wrap_mkostemp(char* p,int flags) {
 CHECK(std::string(p).starts_with("backup/.twrp-digest."));
 operations.push_back("create");++creates;write_calls=0;
 if(fault=="create"||(fault=="split-failure"&&creates==2)){errno=ENOSPC;return -1;}
 destination=archive_path;
 if(scenario.starts_with("split-")){CHECK(creates<=3);destination+=std::vector<std::string>{"000","001","100"}[creates-1];}
 destination+=suffix;
 previous_exists=fs::exists(destination);previous_directory=fs::is_directory(destination);previous_symlink=fs::is_symlink(destination);
 previous_bytes=previous_exists&&!previous_directory?contents(destination):"";
 staged_fd=__real_mkostemp(p,flags);if(staged_fd>=0)CHECK(fcntl(staged_fd,F_GETFD)&FD_CLOEXEC);return staged_fd;
}
extern "C" ssize_t __wrap_write(int fd,const void* p,size_t n) {
 if(fd!=staged_fd)return __real_write(fd,p,n);
 unchanged_publication();
 operations.push_back("write");++write_calls;
 if(fault=="crash-stage"){CHECK(__real_write(fd,p,std::min<size_t>(3,n))==3);_exit(91);}
 if(fault=="zero-write")return 0;
 if(fault=="eintr-write"&&write_calls==1){errno=EINTR;return -1;}
 if(fault=="partial-write-error"&&write_calls>1){errno=ENOSPC;return -1;}
 if(fault=="short-write"||fault=="partial-write-error")n=std::min<size_t>(3,n);
 return __real_write(fd,p,n);
}
extern "C" int __wrap_fsync(int fd) {
 if(fd==staged_fd){unchanged_publication();++file_syncs;operations.push_back("file-sync");if(fault=="file-sync"){errno=EIO;return -1;}if(fault=="file-sync-eintr"&&file_syncs==1){errno=EINTR;return -1;}}
 if(fd==parent_fd){++dir_syncs;operations.push_back("directory-sync");if(fault=="dir-sync"){errno=EIO;return -1;}if(fault=="dir-sync-eintr"&&dir_syncs==1){errno=EINTR;return -1;}}
 if(fd==staged_fd&&fault=="crash-synced-stage"){CHECK(__real_fsync(fd)==0);_exit(91);}
 return __real_fsync(fd);
}
extern "C" int __wrap_close(int fd) {
 if(fd==staged_fd){++closes;operations.push_back("close");staged_fd=-1;int r=__real_close(fd);if(fault=="close"){errno=EIO;return -1;}return r;}
 if(fd==parent_fd)parent_fd=-1;
 return __real_close(fd);
}
extern "C" int __wrap_rename(const char* a,const char* b) {
 if(!std::string(a).starts_with("backup/.twrp-digest."))return __real_rename(a,b);
 operations.push_back("rename");++renames;if(fault=="rename"){errno=EIO;return -1;}
 int r=__real_rename(a,b);if(fault=="crash-rename"&&r==0)_exit(91);return r;
}
static std::string line(const std::string& file) {return expected_hex+"  "+file+"\n";}
static size_t temporaries() {size_t count=0;for(const auto& e:fs::directory_iterator("backup"))if(e.path().filename().string().starts_with(".twrp-digest."))++count;return count;}
static void verify_order() {
 auto pos=[](const std::string& s){auto it=std::find(operations.begin(),operations.end(),s);CHECK(it!=operations.end());return it-operations.begin();};
 CHECK(pos("create")<pos("write")&&pos("write")<pos("metadata")&&pos("metadata")<pos("file-sync")&&pos("file-sync")<pos("close")&&pos("close")<pos("rename")&&pos("rename")<pos("directory-sync"));
}
int main(int argc,char** argv) {
 CHECK(argc==4&&fs::is_regular_file(".fixture"));scenario=argv[1];use_sha2=std::string(argv[2])=="sha256";expected_hex=argv[3];suffix=use_sha2?".sha2":".md5";fault=scenario;
 const std::string basename=scenario=="long-name"?std::string(240,'n')+".win":"data.ext4.win";
 const std::string archive="backup/"+basename,sidecar=archive+suffix,old="previous complete sidecar\n";
 archive_path=archive;if(scenario=="long-name")fs::rename("backup/data.ext4.win",archive);
 const auto input=contents(archive);CHECK(!input.empty());
 if(scenario!="plain-new")put(sidecar,old);
 if(scenario=="symlink"){fs::remove(sidecar);put("unrelated","DO NOT ALTER");fs::create_symlink("../unrelated",sidecar);}
 if(scenario=="target-dir"){fs::remove(sidecar);fs::create_directory(sidecar);put(fs::path(sidecar)/"sentinel","keep");}
 if(scenario=="source-missing")fs::remove(archive);
 if(scenario=="crash-stage"||scenario=="crash-synced-stage"||scenario=="crash-rename"){
  const pid_t child=fork();CHECK(child>=0);if(!child){TwrpDigestDriver::WriteDigest(archive);_exit(90);}
  int status;CHECK(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==91);
  if(scenario!="crash-rename"){
   CHECK(contents(sidecar)==old);CHECK(temporaries()==1);
   auto files=TwrpDigestDriver::GetBackupFiles(archive);CHECK(files&&*files==std::vector<std::string>{archive});
   for(const auto& e:fs::directory_iterator("backup"))if(e.path().filename().string().starts_with(".twrp-digest."))
    CHECK(contents(e.path())==(scenario=="crash-stage"?expected_hex.substr(0,3):line("data.ext4.win")));
  }
  else {CHECK(contents(sidecar)==line("data.ext4.win"));CHECK(temporaries()==0);}
 } else if(scenario=="split-normal"||scenario=="split-failure") {
  fs::remove(archive);fs::remove(sidecar);
  for(const char* part:{"000","001","100"}){put(archive+part,input);put(archive+part+suffix,old);}
  bool ok=TwrpDigestDriver::MakeDigest(archive);CHECK(ok==(scenario=="split-normal"));
  CHECK(contents(archive+"000"+suffix)==line("data.ext4.win000"));
  CHECK(contents(archive+"001"+suffix)==(ok?line("data.ext4.win001"):old));
  CHECK(contents(archive+"100"+suffix)==(ok?line("data.ext4.win100"):old));
  CHECK(temporaries()==0);
 } else if(scenario.starts_with("caller-")) {
  TWPartition part;PartitionSettings settings;settings.part=&part;TWPartitionManager manager;
  fault=scenario=="caller-digest-failure"?"file-sync":"";
  bool ok=manager.BackupPartition(&settings);CHECK(ok==(scenario=="caller-normal"));CHECK(backups==1&&performance==0);
  CHECK(contents(sidecar)==(scenario=="caller-digest-failure"?old:line("data.ext4.win")));
 } else {
  const bool success=scenario=="plain-new"||scenario=="replace"||scenario=="short-write"||scenario=="eintr-write"||scenario=="symlink"||scenario=="file-sync-eintr"||scenario=="dir-sync-eintr"||scenario=="long-name";
  bool ok=TwrpDigestDriver::WriteDigest(archive);
  if(scenario=="retry") { // First fail before publication; second succeeds.
   // Inject via a separate call so no first attempt can silently count as a retry.
   CHECK(ok);fault="file-sync";CHECK(!TwrpDigestDriver::WriteDigest(archive));CHECK(contents(sidecar)==line("data.ext4.win"));fault="";CHECK(TwrpDigestDriver::WriteDigest(archive));
  } else {
   CHECK(ok==success);
   if(scenario=="target-dir")CHECK(contents(fs::path(sidecar)/"sentinel")=="keep");
   else CHECK(contents(sidecar)==(success||scenario=="dir-sync"?line(basename):old));
   if(success){
    CHECK(successes==1&&errors==0);
    if(scenario=="symlink")CHECK(!fs::is_symlink(sidecar)&&contents("unrelated")=="DO NOT ALTER");
    verify_order();CHECK(TwrpDigestDriver::CheckFileDigest(archive));
    if(scenario=="file-sync-eintr")CHECK(file_syncs==2);
    if(scenario=="dir-sync-eintr")CHECK(dir_syncs==2);
   }
   else {CHECK(successes==0);if(scenario!="source-missing")CHECK(errors>0);}
  }
  CHECK(temporaries()==0);
  if(scenario=="symlink")CHECK(!fs::is_symlink(sidecar)&&contents("unrelated")=="DO NOT ALTER");
 }
 if(fs::exists(archive))CHECK(contents(archive)==input);
 printf("PASS %s %s creates=%d file_syncs=%d directory_syncs=%d closes=%d renames=%d\n",argv[2],argv[1],creates,file_syncs,dir_syncs,closes,renames);
}
