#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <filesystem>
#include <format>
#include <fstream>
#include <limits>
#include <map>
#include <memory>
#include <ranges>
#include <string>
#include <vector>
#include <fcntl.h>
#include <linux/fs.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <android-base/file.h>
#include <android-base/hex.h>
#include <android-base/strings.h>
#include <android-base/scopeguard.h>
#include <android-base/unique_fd.h>
#include "data.hpp"
#include "variables.h"
#include "twcommon.h"
#include "twrp_functions.hpp"
#include "twrp_operation_executor.h"
#include "backup_manifest.hpp"
#include "twrp_digest_driver.hpp"
#include "twrp_digest.hpp"
#include "set_metadata.h"
#include "gui2/console/stdio_adapter.h"
namespace fs=std::filesystem;
#define CHECK(x) do {if(!(x)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
constexpr uint64_t kMiB=1024*1024;
constexpr int ENCRYPTED=2;
constexpr int UNCOMPRESSED=0,COMPRESSED=1;
static fs::path root;
static std::string scenario;
static std::map<std::string,std::string> settings;
static std::vector<std::string> restored,events;
static int digests=0,performance=0,completed=0;
static bool mount_ok=true;
static uint64_t progress_total=0;
void DataManager::SetValue(const std::string& k,const std::string& v){settings[k]=v;}
void DataManager::SetValue(const std::string& k,int v){settings[k]=std::to_string(v);}
void DataManager::GetValue(const std::string& k,std::string& v){v=settings[k];}
void DataManager::GetValue(const std::string& k,int& v){v=settings[k].empty()?0:std::stoi(settings[k]);}
void DataManager::SetProgress(double){}
struct ProgressTracking {
 uint64_t current=0,bytes=0;
 explicit ProgressTracking(uint64_t total){progress_total=total;}
 void SetPartitionSize(uint64_t n){current=n;bytes=0;}
 void UpdateSize(uint64_t n){CHECK(n<=current);bytes=n;}
 void UpdateDisplayDetails(bool){}
};
enum class PartitionManagerOp{kBackup,kRestore};
struct TWPartition;
struct PartitionSettings {
 TWPartition* part=nullptr;std::string backup_folder;bool generate_digest=false;
 uint64_t total_restore_size=0;int partition_count=0;ProgressTracking* progress=nullptr;
 PartitionManagerOp pm_method=PartitionManagerOp::kBackup;
};
struct TWPartition {
 std::string backup_name_,backup_file_name_,backup_display_name_,mount_point_,backup_path_;
 std::string current_file_system_="emmc",display_name_="fixture",actual_block_device_,sub_partition_of_;
 bool has_sub_partition_=false,is_sub_partition_=false,is_encrypted_=false,mount_read_only_=false,is_present_=true;
 uint64_t backup_size_=0;
 void SetBackupFileName(const std::string& s){backup_file_name_=s;}
 bool Restore(PartitionSettings*);
 uint64_t GetRestoreSize(PartitionSettings*);
 std::string GetRestoreFileSystem(PartitionSettings*);
 static bool IsFileSystem(std::string_view);
 bool RestoreImage(PartitionSettings*);
 bool RawReadWrite(const PartitionSettings*) const;
};
struct TWPartitionManager {
 std::atomic_bool stop_backup=false;std::vector<TWPartition*> partitions_;
 // RUN_RESTORE_DECL
 bool RestorePartition(PartitionSettings*) const;
 void SetRestoreFiles(const std::string&) const;
 int CheckBackupCancel() const;
 bool MountCurrentStorage(bool)const{return mount_ok;}
 TWPartition* FindPartitionByPath(const std::string& s)const {
  for(auto* p:partitions_)if(s==p->mount_point_||s==p->backup_name_)return p;
  return nullptr;
 }
 static std::string GetAndroidRootPath(){return "/fixture-system";}
 bool UnmountByPath(const std::string&,bool)const{return true;}
 void UnmountMainPartitions()const{}
 void UpdateSystemDetails()const{}
} PartitionManager;
void console_event(const std::string& key){
 events.push_back(key);
 if(key=="digest_matched"){
  CHECK(restored.empty());++digests;
  if(scenario=="cancel-preflight")PartitionManager.stop_backup=true;
 }
 if(key=="restore_completed")++completed;
}
twrp_operation_executor& twrp_operation_executor::instance(){static twrp_operation_executor e;return e;}
namespace UnitConversion {std::string FormatBytes(uint64_t n){return std::to_string(n);}}
int tw_set_default_metadata(const char*){return 0;}
int tw_get_default_metadata(const char*){return 0;}
namespace TWFunc {
std::string GetFilename(const std::string& s){return fs::path(s).filename().string();}
bool IsPathExists(const std::string& s){std::error_code ec;return fs::exists(s,ec);}
bool WriteToFile(const std::string& p,const std::string& s){std::ofstream f(p);f<<s;f.close();return !f.fail();}
uint64_t GetFileSize(const std::string& s){std::error_code ec;auto n=fs::file_size(s,ec);return ec?0:n;}
// FILE_TYPE_METHOD
void SetPerformanceMode(bool on){performance+=on?1:-1;CHECK(performance>=0);}
std::vector<std::string> SplitString(const std::string& s,char d,bool skip){
 std::vector<std::string> v;size_t i=0;
 while(i<=s.size()){auto e=s.find(d,i);auto p=s.substr(i,e==std::string::npos?e:e-i);if(!skip||!p.empty())v.push_back(p);if(e==std::string::npos)break;i=e+1;}return v;
}
}
namespace android::base {
bool ReadFully(borrowed_fd fd,void* data,size_t count){char* out=static_cast<char*>(data);while(count){ssize_t n=TEMP_FAILURE_RETRY(read(fd.get(),out,count));if(n<=0)return false;out+=n;count-=n;}return true;}
bool ReadFdToString(borrowed_fd fd,std::string* out){out->clear();char b[4096];ssize_t n;while((n=TEMP_FAILURE_RETRY(read(fd.get(),b,sizeof b)))>0)out->append(b,n);return n==0;}
bool EqualsIgnoreCase(std::string_view a,std::string_view b){return a.size()==b.size()&&std::equal(a.begin(),a.end(),b.begin(),[](char x,char y){return tolower(x)==tolower(y);});}
std::string HexString(const void* ptr,size_t n){const auto*b=static_cast<const unsigned char*>(ptr);std::string s;for(size_t i=0;i<n;++i)s+=std::format("{:02x}",b[i]);return s;}
}
extern "C" void __wrap_sync(){} // Do not sync the host for the old digest implementation.
static std::string contents(const fs::path& p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
static void put(const fs::path& p,const std::string& bytes){std::ofstream f(p,std::ios::binary);f<<bytes;CHECK(bool(f));}
static void checksum(const fs::path& p,bool md5=false,bool upper=false){
 TwrpDigest d(md5?TwrpDigest::Algorithm::kMd5:TwrpDigest::Algorithm::kSha256);
 const auto b=contents(p);d.Update(b.data(),b.size());std::string hash=d.HexDigest();
 if(upper)for(char&c:hash)c=toupper(c);
 put(p.string()+(md5?".md5":".sha2"),hash+"  "+p.filename().string()+"\n");
}
static std::string fdpath(int fd){char link[64],buf[4096];snprintf(link,sizeof link,"/proc/self/fd/%d",fd);ssize_t n=readlink(link,buf,sizeof(buf)-1);CHECK(n>=0);buf[n]=0;return buf;}
static bool targetfd(int fd){return fdpath(fd).starts_with((root/"targets").string()+"/");}
static int fixture_open(const char* p,int flags,...){
 auto actual=fs::weakly_canonical(fs::absolute(p));CHECK(actual.string().starts_with(root.string()+"/"));
 mode_t m=0;if(flags&O_CREAT){va_list a;va_start(a,flags);m=va_arg(a,int);va_end(a);}
 return open(p,flags,m);
}
static int fixture_fstat(int fd,struct stat* s){int rc=fstat(fd,s);if(rc==0&&targetfd(fd)&&scenario!="target-ordinary")s->st_mode=(s->st_mode&07777)|S_IFBLK;return rc;}
static int fixture_ioctl(int fd,unsigned long request,...){
 CHECK(targetfd(fd)&&request==BLKGETSIZE64);va_list a;va_start(a,request);auto* n=va_arg(a,uint64_t*);va_end(a);
 if(scenario=="target-ioctl-error"){errno=EIO;return -1;}
 struct stat st{};CHECK(fstat(fd,&st)==0);*n=st.st_size;return 0;
}
// File-archive extraction is a boundary substitute. Raw-image restore below
// calls the actual RestoreImage and RawReadWrite bodies against fixture files.
bool TWPartition::Restore(PartitionSettings* ps){
 restored.push_back(backup_name_);
 CHECK(ps->part==this&&performance==1);
 if(scenario=="restore-failure"&&backup_name_=="b")return false;
 if(scenario=="parent-child-selected")CHECK(ps->partition_count==3);
 bool ok;
 if(GetRestoreFileSystem(ps)=="emmc")ok=RestoreImage(ps);
 else {
  const auto full=fs::path(ps->backup_folder)/backup_file_name_;
  auto file=fs::exists(full)?full:fs::path(full.string()+"000");
  ok=fs::is_regular_file(file);
  if(ok)put(actual_block_device_,contents(file));
 }
 if((scenario=="cancel-between"&&backup_name_=="a")||(scenario=="cancel-last"&&backup_name_=="b"))PartitionManager.stop_backup=true;
 return ok;
}
uint64_t TWPartition::GetRestoreSize(PartitionSettings* ps){
 if(scenario=="size-overflow")return std::numeric_limits<uint64_t>::max();
 auto p=fs::path(ps->backup_folder)/backup_file_name_;
 return TWFunc::GetFileSize(fs::exists(p)?p.string():p.string()+"000");
}
#define open fixture_open
#define fstat fixture_fstat
#define ioctl fixture_ioctl
// PRODUCTION_METHODS
#undef open
#undef fstat
#undef ioctl

int main(int argc,char** argv){
 CHECK(argc==2);scenario=argv[1];root=fs::current_path();
 CHECK(root.string().starts_with("/tmp/dijun-restore-session-")&&fs::exists(root/".fixture"));
 fs::create_directory("backup");fs::create_directory("targets");
 TWPartition a,b,c;
 int index=0;for(auto* p:{&a,&b,&c}){
  p->backup_name_=std::string(1,'a'+index++);p->mount_point_="/"+p->backup_name_;
  p->backup_path_=p->mount_point_;p->backup_display_name_=p->backup_name_;
  p->actual_block_device_=(root/"targets"/p->backup_name_).string();
  put(p->actual_block_device_,std::string(4096,'O'));
  p->backup_file_name_=p->backup_name_+".emmc.win";
  put(root/"backup"/p->backup_file_name_,std::string(2048,p->backup_name_[0]));
  checksum(root/"backup"/p->backup_file_name_);
  PartitionManager.partitions_.push_back(p);
 }
 if(scenario=="manifest-incomplete") put(root/"backup"/twrp_backup_manifest::kName,
     std::string(twrp_backup_manifest::kHeader)+"INCOMPLETE\n");
 if(scenario=="manifest-mismatch") put(root/"backup"/twrp_backup_manifest::kName,
     std::string(twrp_backup_manifest::kHeader)+"COMPLETE\n999\ta.emmc.win\n999\tb.emmc.win\n");
 const auto ap=root/"backup"/a.backup_file_name_, bp=root/"backup"/b.backup_file_name_, cp=root/"backup"/c.backup_file_name_;
 settings["tw_restore_selected"]="/a;/b;";settings[TW_SKIP_DIGEST_CHECK_VAR]="1";
 settings["tw_file_progress"]="old";
 if(scenario.starts_with("list-")){
  const auto base=root/"backup"/"b.ext4.win";
  fs::remove(bp);fs::remove(bp.string()+".sha2");
  if(scenario=="list-fifo")CHECK(mkfifo(base.c_str(),0600)==0);
  else if(scenario=="list-split-fifo"){put(base.string()+"000","archive");CHECK(mkfifo((base.string()+"100").c_str(),0600)==0);}
  else if(scenario=="list-directory")fs::create_directory(base);
  else if(scenario=="list-symlink")fs::create_symlink(ap,base);
  else if(scenario=="list-empty")put(base,"");
  else if(scenario=="list-gap"){put(base.string()+"000","archive");put(base.string()+"002","tail");}
  else if(scenario=="list-encrypted-thread"){put(base.string()+"000","plain");put(base.string()+"100","OAencrypted");}
  else if(scenario=="list-split"){put(base.string()+"000","first");put(base.string()+"001","second");}
  else put(base,"archive");
  const bool valid=scenario=="list-normal"||scenario=="list-split"||scenario=="list-encrypted-thread";
  PartitionManager.SetRestoreFiles((root/"backup").string());
  if(valid){CHECK(b.backup_file_name_=="b.ext4.win");CHECK(!settings["tw_restore_selected"].empty());}
  else{CHECK(settings["tw_restore_selected"].empty());CHECK(settings["tw_restore_list"].empty());CHECK(a.backup_file_name_.empty()&&b.backup_file_name_.empty()&&c.backup_file_name_.empty());}
  CHECK(settings["tw_restore_encrypted"]==(scenario=="list-encrypted-thread"?"1":"0"));
  CHECK(restored.empty());CHECK(contents(a.actual_block_device_)==std::string(4096,'O'));CHECK(contents(b.actual_block_device_)==std::string(4096,'O'));
  puts("PASS: restore list validated before real archive header probe; targets unchanged");return 0;
 }
 bool expected=true;bool no_write=false;
 if(scenario=="after-cancel")PartitionManager.stop_backup=true;
 if(scenario=="unknown-first"||scenario=="unknown-last")settings["tw_restore_selected"]=scenario=="unknown-first"?"/missing;/a;":"/a;/missing;";
 if(scenario=="empty-selection")settings["tw_restore_selected"]="";
 if(scenario=="no-delimiter")settings["tw_restore_selected"]="/a;/b";
 if(scenario=="duplicates")settings["tw_restore_selected"]="/a;/b;/a;";
 if(scenario.starts_with("child-")||scenario.starts_with("parent-child")){
  a.has_sub_partition_=true;c.is_sub_partition_=true;c.sub_partition_of_="/a";
 }
 if(scenario=="parent-child-selected")settings["tw_restore_selected"]="/c;/a;/b;/c;";
 if(scenario=="child-filesystem"){
  c.current_file_system_="erofs";c.backup_file_name_="c.ext4.win";
  fs::rename(cp,root/"backup"/c.backup_file_name_);checksum(root/"backup"/c.backup_file_name_);
 }
 if(scenario=="second-bad-digest")put(bp,"tampered");
 if(scenario=="child-bad-digest")put(cp,"tampered");
 if(scenario=="second-missing"||scenario=="missing-without-digest")fs::remove(bp);
 if(scenario=="missing-without-digest")settings[TW_SKIP_DIGEST_CHECK_VAR]="0";
 if(scenario=="child-removed")fs::remove(cp);
 if(scenario=="child-readonly")c.mount_read_only_=true;
 if(scenario=="second-readonly")b.mount_read_only_=true;
 if(scenario=="second-absent")b.is_present_=false;
 if(scenario=="second-oversized")put(b.actual_block_device_,std::string(100,'O'));
 if(scenario=="target-missing")fs::remove(b.actual_block_device_);
 if(scenario=="source-empty")put(bp,"");
 if(scenario=="source-symlink"){fs::remove(bp);fs::create_symlink(ap,bp);}
 if(scenario=="source-directory"){fs::remove(bp);fs::create_directory(bp);}
 if(scenario=="source-fifo"){fs::remove(bp);CHECK(mkfifo(bp.c_str(),0600)==0);}
 if(scenario=="second-fifo-sidecar"){
  fs::remove(bp.string()+".sha2");CHECK(mkfifo((bp.string()+".sha2").c_str(),0600)==0);
 }
 if(scenario=="second-oversized-sidecar"){
  put(bp.string()+".sha2",contents(bp.string()+".sha2")+std::string(65536,' '));
 }
 if(scenario=="invalid-filesystem"){b.backup_file_name_="b.unknown.win";fs::rename(bp,root/"backup"/b.backup_file_name_);}
 if(scenario=="traversal-name")b.backup_file_name_="../backup/b.emmc.win";
 if(scenario=="size-overflow"){
  for(auto*p:{&a,&b}){auto old=root/"backup"/p->backup_file_name_;p->backup_file_name_=p->backup_name_+".ext4.win";fs::rename(old,root/"backup"/p->backup_file_name_);}
 }
 if(scenario=="mount-failure")mount_ok=false;
 if(scenario=="stale-open"||scenario=="bad-open"){
  a.has_sub_partition_=true;c.is_sub_partition_=true;c.sub_partition_of_="/a";
  PartitionManager.SetRestoreFiles((root/"backup").string());
  fs::create_directory("next");put(root/"next"/a.backup_file_name_,contents(ap));
  PartitionManager.SetRestoreFiles((root/(scenario=="stale-open"?"next":"absent")).string());
  CHECK(b.backup_file_name_.empty()&&c.backup_file_name_.empty());
  if(scenario=="bad-open"){CHECK(settings["tw_restore_selected"].empty());return 0;}
  CHECK(PartitionManager.RunRestore((root/"next").string()));CHECK(restored==std::vector<std::string>{"a"});return 0;
 }
 if(scenario.starts_with("digest-")||scenario.starts_with("make-")){
  bool make=scenario.starts_with("make-");fs::path file=ap;
  if(scenario=="digest-missing-file"||scenario=="make-missing")fs::remove(ap);
  if(scenario=="digest-no-sidecar")fs::remove(ap.string()+".sha2");
  if(scenario=="digest-malformed")put(ap.string()+".sha2","not a digest\n");
  if(scenario=="digest-wrong-name"){auto text=contents(ap.string()+".sha2");text.replace(text.find("a.emmc.win"),10,"other.win");put(ap.string()+".sha2",text);}
  if(scenario=="digest-uppercase")checksum(ap,false,true);
  if(scenario=="digest-md5"){fs::remove(ap.string()+".sha2");checksum(ap,true);}
  if(scenario.starts_with("digest-fifo")){
   fs::remove(ap.string()+".sha2");
   const auto suffix=scenario=="digest-fifo"?".sha2":scenario=="digest-fifo-sha256"?".sha256":scenario=="digest-fifo-md5"?".md5":".md5sum";
   CHECK(mkfifo((ap.string()+suffix).c_str(),0600)==0);
  }
  if(scenario=="digest-directory"){fs::remove(ap.string()+".sha2");fs::create_directory(ap.string()+".sha2");}
  if(scenario=="digest-limit"||scenario=="digest-oversized"){
   auto text=contents(ap.string()+".sha2");text.resize(65536+(scenario=="digest-oversized"?1:0),' ');put(ap.string()+".sha2",text);
  }
  if(scenario=="digest-symlink"){
   fs::rename(ap.string()+".sha2",root/"checksum.txt");fs::create_symlink(root/"checksum.txt",ap.string()+".sha2");
  }
  if(scenario=="make-threaded"){
   fs::remove(ap);file=root/"backup/data.ext4.win";
   for(auto s:{"000","001","100","200","201"})put(file.string()+s,"fixture "+std::string(s));
  }
  bool result=make?TwrpDigestDriver::MakeDigest(file.string()):TwrpDigestDriver::CheckDigest(file.string());
  expected=scenario!="digest-missing-file"&&scenario!="make-missing"&&scenario!="digest-malformed"&&scenario!="digest-wrong-name";
  if(scenario.starts_with("digest-fifo")||scenario=="digest-directory"||scenario=="digest-oversized")expected=false;
  CHECK(result==expected);
  if(!expected&&scenario.starts_with("digest-"))CHECK(std::ranges::find(events,"no_digest")==events.end());
  if(scenario=="make-threaded")for(auto s:{"000","001","100","200","201"}){
   CHECK(fs::is_regular_file(file.string()+s+".md5"));CHECK(TwrpDigestDriver::CheckFileDigest(file.string()+s));
  }
  CHECK(restored.empty());return 0;
 }
 if(scenario.starts_with("split-")){
  fs::remove(bp);b.backup_file_name_=scenario=="split-raw"?"b.emmc.win":"b.ext4.win";
  auto prefix=(root/"backup"/b.backup_file_name_).string();
  std::vector<std::string> suffixes={"000","001"};
  if(scenario=="split-threaded"||scenario=="split-bad-thread")suffixes={"000","001","100","200","201"};
  if(scenario=="split-missing-first")suffixes={"100"};
  if(scenario=="split-gap")suffixes={"000","002"};
  if(scenario=="split-thread-gap")suffixes={"000","101"};
  if(scenario=="split-unsupported-thread")suffixes={"000","900"};
  if(scenario=="split-long-index")suffixes={"000","0001"};
  for(auto s:suffixes){put(prefix+s,"part-"+s);checksum(prefix+s);}
  if(scenario=="split-ambiguous"){put(prefix,"single");checksum(prefix);}
  if(scenario=="split-bad-thread")put(prefix+"200","tampered");
 }
 const std::vector<std::string> failures={"manifest-incomplete","manifest-mismatch","unknown-first","unknown-last","empty-selection","child-bad-digest",
 "second-bad-digest","second-missing","missing-without-digest","child-removed","child-readonly","second-readonly",
 "second-absent","second-oversized","target-missing","target-ordinary","target-ioctl-error","source-empty",
 "source-symlink","source-directory","source-fifo","invalid-filesystem","split-raw","traversal-name","size-overflow",
 "mount-failure","cancel-preflight","split-bad-thread","split-missing-first","split-gap","split-thread-gap",
 "split-ambiguous","split-unsupported-thread","split-long-index","second-fifo-sidecar","second-oversized-sidecar"};
 no_write=std::ranges::find(failures,scenario)!=failures.end();expected=!no_write;
 if(scenario=="restore-failure"||scenario=="cancel-between"||scenario=="cancel-last")expected=false;
 std::map<std::string,std::string> previous;for(auto*p:{&a,&b,&c})if(fs::exists(p->actual_block_device_))previous[p->actual_block_device_]=contents(p->actual_block_device_);
 bool result=PartitionManager.RunRestore((root/"backup").string());
 CHECK(result==expected);CHECK(performance==0);CHECK(completed==(expected?1:0));
 CHECK(settings["tw_file_progress"].empty());
 if(no_write){CHECK(restored.empty());for(auto&[p,v]:previous)CHECK(contents(p)==v);}
 else {
  CHECK(restored.size()==(scenario=="cancel-between"?1:scenario.starts_with("parent-child")||scenario=="child-filesystem"?3:2));
  CHECK(contents(a.actual_block_device_).substr(0,2048)==std::string(2048,'a'));
  if(expected&&!(scenario.starts_with("split-")))CHECK(contents(b.actual_block_device_).substr(0,2048)==std::string(2048,'b'));
  if(scenario=="child-filesystem")CHECK(contents(c.actual_block_device_)==std::string(2048,'c'));
  if(scenario=="split-threaded")CHECK(digests==6);
  if(scenario=="normal")CHECK(progress_total==4096);
 }
 puts("PASS: production preflight, digest and restore session");
}
