#include <algorithm>
#include <array>
#include <barrier>
#include <thread>
#include <mutex>
#include <cassert>
#include <cerrno>
#include <csignal>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <map>
#include <string>
#include <vector>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/wait.h>
#include <sys/xattr.h>
#include <linux/xattr.h>
#include <linux/capability.h>
#include <unistd.h>
#include <zlib.h>
#include <android-base/file.h>
#include <android-base/unique_fd.h>
#include "twrpTar.hpp"
#include "tarWrite.hpp"
#include "oaes/oaes.hpp"
#include "infomanager.hpp"
#include "gui2/console/stdio_adapter.h"
#include "twcommon.h"
#include "fscrypt_policy.h"
using namespace std;
namespace fs=std::filesystem;
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL %d: %s errno=%d\n",__LINE__,#x,errno);exit(1);}}while(0)
static bool security_fixture=false;
static string security_fault;
static bool special_fixture=false;
static mode_t special_type;
extern "C" int __wrap_mknod(const char* path,mode_t mode,dev_t device){
 CHECK(special_fixture&&string(path)=="/src/node"&&(mode&S_IFMT)==special_type);
 CHECK(major(device)==1&&minor(device)==3);
 int fd=open("/backup/mknod-called",O_WRONLY|O_CREAT,0600);CHECK(fd>=0);CHECK(close(fd)==0);
 errno=EEXIST;return -1;
}
static const char security_context[]="u:object_r:system_file:s0";
static vfs_cap_data security_cap{};
extern "C" int __real_lgetfilecon(const char*,char**);
extern "C" int __real_lsetfilecon(const char*,const char*);
extern "C" ssize_t __real_getxattr(const char*,const char*,void*,size_t);
extern "C" int __real_setxattr(const char*,const char*,const void*,size_t,int);
static void metadata_call(const char* name){
 int fd=open("/backup/security-calls",O_CREAT|O_APPEND|O_WRONLY,0600);CHECK(fd>=0);
 CHECK(write(fd,name,strlen(name))==static_cast<ssize_t>(strlen(name)));CHECK(close(fd)==0);
}
extern "C" int __wrap_lgetfilecon(const char* path,char** value){
 if(!security_fixture)return __real_lgetfilecon(path,value);
 if(string(path)=="/src/dir/file0"){*value=strdup(security_context);CHECK(*value);return strlen(*value)+1;}
 errno=ENODATA;return -1;
}
extern "C" int __wrap_lsetfilecon(const char* path,const char* value){
 if(!security_fixture)return __real_lsetfilecon(path,value);
 CHECK(fs::path(path).lexically_normal()=="/src/dir/file0"&&!strcmp(value,security_context));metadata_call("label\n");
 if(security_fault=="label-error"){errno=EPERM;return -1;}
 return __real_setxattr(path,"user.fixture_selinux",value,strlen(value)+1,0);
}
extern "C" ssize_t __wrap_getxattr(const char* path,const char* name,void* value,size_t size){
 if(security_fixture&&!strcmp(name,XATTR_NAME_CAPS)){
  if(string(path)=="/src/dir/file0"){CHECK(size>=sizeof security_cap);memcpy(value,&security_cap,sizeof security_cap);return sizeof security_cap;}
  errno=ENODATA;return -1;
 }
 return __real_getxattr(path,name,value,size);
}
extern "C" int __wrap_setxattr(const char* path,const char* name,const void* value,size_t size,int flags){
 if(security_fixture&&!strcmp(name,XATTR_NAME_CAPS)){
  CHECK(fs::path(path).lexically_normal()=="/src/dir/file0"&&size==sizeof security_cap&&!memcmp(value,&security_cap,size));metadata_call("cap\n");
  if(security_fault=="cap-error"){errno=EIO;return -1;}
  return __real_setxattr(path,"user.fixture_capability",value,size,flags);
 }
 return __real_setxattr(path,name,value,size,flags);
}
static bool directory_fixture=false;
static string directory_fault;
static constexpr time_t root_time=1600000000, child_time=1600000100;
extern "C" int __real_open(const char*,int,...);
extern "C" int __wrap_open(const char* path,int flags,...){
 mode_t mode=0;
 if(flags&O_CREAT){va_list ap;va_start(ap,flags);mode=va_arg(ap,int);va_end(ap);}
 if(directory_fixture&&(flags&O_DIRECTORY)&&(flags&O_NOFOLLOW)&&
    fs::path(path).lexically_normal()=="/src/dir"&&
    (directory_fault=="symlink"||directory_fault=="replace")){
  CHECK(rename("/src/dir","/src/held")==0);
  if(directory_fault=="symlink")CHECK(symlink("held","/src/dir")==0);
  else CHECK(mkdir("/src/dir",0700)==0);
  metadata_call("identity-replaced\n");
 }
 return __real_open(path,flags,mode);
}
extern "C" int __real_futimens(int,const struct timespec[2]);
extern "C" int __wrap_futimens(int fd,const struct timespec times[2]){
 if(!directory_fixture)return __real_futimens(fd,times);
 struct stat st{};CHECK(fstat(fd,&st)==0&&S_ISDIR(st.st_mode));
 CHECK(times[0].tv_sec==times[1].tv_sec&&times[0].tv_nsec==0&&times[1].tv_nsec==0);
 CHECK(times[1].tv_sec==root_time||times[1].tv_sec==child_time);
 metadata_call("directory-time\n");
 if(directory_fault=="error"){errno=EIO;return -1;}
 return __real_futimens(fd,times);
}
static bool application_xattrs=false;
static string application_xattr_fault;
extern "C" ssize_t __real_llistxattr(const char*,char*,size_t);
extern "C" ssize_t __wrap_llistxattr(const char* path,char* names,size_t size){
 if(application_xattrs&&application_xattr_fault=="read-error"&&string(path)=="/src/dir/file0"){
  metadata_call("application-xattr-read-error\n");errno=EACCES;return -1;
 }
 return __real_llistxattr(path,names,size);
}
extern "C" int __real_lsetxattr(const char*,const char*,const void*,size_t,int);
extern "C" int __wrap_lsetxattr(const char* path,const char* name,const void* data,size_t size,int flags){
 if(application_xattrs&&string(name)=="user.fixture_blob"&&application_xattr_fault=="write-error"){
  metadata_call("application-xattr-error\n");errno=ENOSPC;return -1;
 }
 return __real_lsetxattr(path,name,data,size,flags);
}
bool datamedia=false;
extern "C" {
bool fscrypt_set_mode(){return true;}
bool fscrypt_policy_get_struct(const char*,fscrypt_policy_v2*){return false;}
bool fscrypt_policy_set_struct(const char*,const fscrypt_policy_v2*){return false;}
bool lookup_ref_key(fscrypt_policy_v2*,uint8_t*){return false;}
bool lookup_ref_tar(const uint8_t*,uint8_t*){return false;}
void bytes_to_hex(const uint8_t* p,size_t n,char* r){for(size_t i=0;i<n;++i)sprintf(r+i*2,"%02x",p[i]);}
}
namespace TWFunc {
 bool IsPathExists(const string& p){return fs::exists(p);}
 uint64_t GetFileSize(const string& p){error_code e;auto n=fs::file_size(p,e);return e?0:n;}
 string RemoveTrailingSlashes(const string& p){auto n=p.find_last_not_of('/');return n==string::npos?"/":p.substr(0,n+1);}
 vector<string> SplitString(const string& s,char d,bool skip){vector<string> out;size_t a=0;for(size_t b=0;b<=s.size();++b)if(b==s.size()||s[b]==d){if(!skip||b>a)out.push_back(s.substr(a,b-a));a=b+1;}return out;}
 int ExecCmd(const string&,string&,bool){return -1;}
}
// PRODUCTION_FUNCTIONS
string read_file(const fs::path& p){ifstream f(p,ios::binary);CHECK(f.good());return string(istreambuf_iterator<char>(f),{});}
void write_file(const fs::path& p,const string& s){ofstream f(p,ios::binary);f<<s;CHECK(f.good());}
void transform(bool encrypt,const fs::path& from,const fs::path& to){
 pid_t child=fork();CHECK(child>=0);
 if(child==0){int input=open(from.c_str(),O_RDONLY);int output=open(to.c_str(),O_WRONLY|O_CREAT|O_TRUNC,0600);if(input<0||output<0)_exit(100);
  if(dup2(input,0)<0||dup2(output,1)<0)_exit(101);close(input);close(output);
  if(encrypt)TWFunc::AesEncryptStream("fixture-password");else TWFunc::AesDecryptStream("fixture-password");_exit(0);
 }
 int status;CHECK(waitpid(child,&status,0)==child);CHECK(WIFEXITED(status)&&WEXITSTATUS(status)==0);
}
int main(int argc,char** argv){
 CHECK(argc==2);string scenario=argv[1];CHECK(fs::exists(".fixture"));CHECK(chroot(".")==0);CHECK(chdir("/")==0);
 setvbuf(stdout,nullptr,_IONBF,0);signal(SIGPIPE,SIG_IGN);
 if(scenario.starts_with("read-")){
  array<char,512> data{};
  if(scenario=="read-invalid-fd"){CHECK(readArchive(-1,data.data(),data.size())==-1);CHECK(errno==EBADF);return 0;}
  int pipefd[2];CHECK(pipe(pipefd)==0);
  struct sigaction action{};action.sa_handler=+[](int){};sigemptyset(&action.sa_mask);CHECK(sigaction(SIGALRM,&action,nullptr)==0);
  pid_t child=fork();CHECK(child>=0);
  if(child==0){close(pipefd[0]);if(scenario=="read-eintr")usleep(50000);
   array<char,512> block;block.fill('Z');
   if(write(pipefd[1],block.data(),17)!=17)_exit(101);
   usleep(20000);
   if(scenario!="read-truncated" && write(pipefd[1],block.data()+17,495)!=495)_exit(102);
   close(pipefd[1]);_exit(0);
  }
  close(pipefd[1]);if(scenario=="read-eintr")ualarm(5000,0);
  const auto count=readArchive(pipefd[0],data.data(),data.size());
  // Keep the pipe open until the writer finishes, also in negative controls.
  int status;while(waitpid(child,&status,0)<0)CHECK(errno==EINTR);
  CHECK(WIFEXITED(status)&&WEXITSTATUS(status)==0);close(pipefd[0]);
  const auto expected=scenario=="read-truncated"?17:512;
  CHECK(count==expected);CHECK(string(data.data(),count)==string(expected,'Z'));
  puts("PASS tar pipe read contract");return 0;
 }
 if(scenario=="buffer-parallel"){
  std::barrier barrier(2);std::mutex calls;
  auto worker=[&](int id){
   int fd=open(("/buffer"+to_string(id)).c_str(),O_CREAT|O_WRONLY,0600);CHECK(fd>=0);
   int progress=open(("/progress"+to_string(id)).c_str(),O_CREAT|O_WRONLY,0600);CHECK(progress>=0);
   {lock_guard lock(calls);init_libtar_buffer(4096,progress);}
   barrier.arrive_and_wait();array<char,512> block;block.fill('A'+id);
   for(int n=0;n<6;++n){
    {lock_guard lock(calls);CHECK(write_libtar_buffer(fd,block.data(),block.size())==512);}
    barrier.arrive_and_wait();
   }
   {lock_guard lock(calls);flush_libtar_buffer(fd);}
   barrier.arrive_and_wait();block.fill(0);
   for(int n=0;n<2;++n){
    {lock_guard lock(calls);CHECK(write_libtar_buffer(fd,block.data(),block.size())==512);}
    barrier.arrive_and_wait();
   }
   {lock_guard lock(calls);free_libtar_buffer();}close(fd);close(progress);
  };
  thread a(worker,0),b(worker,1);a.join();b.join();
  CHECK(read_file("/buffer0")==string(3072,'A')+string(1024,0));
  CHECK(read_file("/buffer1")==string(3072,'B')+string(1024,0));
  puts("PASS independent archive buffers");return 0;
 }
 if(scenario.starts_with("wait-")){
  int status=0;
  if(scenario=="wait-not-child"){CHECK(TWFunc::WaitForChild(getpid(),&status,"not child")!=0);return 0;}
  if(scenario=="wait-invalid-pid"){CHECK(TWFunc::WaitForChild(0,&status,"invalid")!=0);return 0;}
  struct sigaction action{};action.sa_handler=+[](int){};sigemptyset(&action.sa_mask);CHECK(sigaction(SIGALRM,&action,nullptr)==0);
  pid_t child=fork();CHECK(child>=0);if(child==0){usleep(50000);if(scenario=="wait-signalled")raise(SIGTERM);_exit(scenario=="wait-nonzero"?7:0);}
  if(scenario=="wait-eintr")ualarm(5000,0);
  int result=TWFunc::WaitForChild(child,&status,"fixture wait");
  CHECK((result==0)==(scenario=="wait-eintr"));puts("PASS child wait status");return 0;
 }
 if(scenario.find("-special-")!=string::npos){
  special_fixture=true;special_type=scenario.ends_with("-char")?S_IFCHR:S_IFBLK;
  fs::create_directory("/src");fs::create_directory("/backup");
  write_file("/src/node","EXISTING ORDINARY FILE");CHECK(chmod("/src/node",0640)==0);
  struct stat before{},after{};CHECK(stat("/src/node",&before)==0);
  TAR* handle=nullptr;CHECK(tar_open(&handle,"/backup/plain",nullptr,O_WRONLY|O_CREAT|O_TRUNC,0600,TAR_GNU)==0);
  th_set_path(handle,"node");handle->th_buf.typeflag=special_type==S_IFCHR?CHRTYPE:BLKTYPE;
  th_set_device(handle,makedev(1,3));th_set_mode(handle,0600);th_set_mtime(handle,1600000000);th_set_size(handle,0);
  CHECK(th_write(handle)==0&&tar_append_eof(handle)==0&&tar_close(handle)==0);
  string input="/backup/plain";const string archive="/backup/data.ext4.win";
  if(scenario.starts_with("gzip")||scenario.starts_with("both")){
   string data=read_file(input);gzFile gz=gzopen("/backup/compressed","wb");CHECK(gz);
   CHECK(gzwrite(gz,data.data(),data.size())==static_cast<int>(data.size()));CHECK(gzclose(gz)==Z_OK);input="/backup/compressed";
  }
  if(scenario.starts_with("aes")||scenario.starts_with("both"))transform(true,input,archive);else fs::copy_file(input,archive);
  ProgressTracking progress(512);PartitionSettings settings;settings.progress=&progress;
  twrpTar restore;restore.setdir("/src");restore.setfn(archive);restore.setpassword("fixture-password");restore.part_settings=&settings;
  CHECK(restore.extractTarFork()!=0);CHECK(fs::exists("/backup/mknod-called"));
  CHECK(stat("/src/node",&after)==0&&before.st_ino==after.st_ino&&before.st_mode==after.st_mode&&before.st_mtime==after.st_mtime);
  CHECK(read_file("/src/node")=="EXISTING ORDINARY FILE");
  puts("PASS special-file failure reaches codec/fork parent without changing existing file");return 0;
 }
 if(scenario.find("-path")!=string::npos){
  const bool split=scenario.ends_with("-split"), encrypted=scenario.starts_with("aes")||scenario.starts_with("both");
  const bool compressed=scenario.starts_with("gzip")||scenario.starts_with("both");
  const bool symlink_case=scenario.find("-symlink")!=string::npos;
  fs::create_directory("/src");fs::create_directory("/outside");fs::create_directory("/backup");
  write_file("/outside/keep","DO NOT MODIFY");
  if(symlink_case)CHECK(symlink("/outside","/src/jump")==0);
  auto volume=[&](const string& out,const string& name){
   TAR* handle=nullptr;CHECK(tar_open(&handle,"/backup/plain",nullptr,O_WRONLY|O_CREAT|O_TRUNC,0600,TAR_GNU)==0);
   th_set_path(handle,const_cast<char*>(name.c_str()));handle->th_buf.typeflag=REGTYPE;th_set_size(handle,0);
   CHECK(th_write(handle)==0&&tar_append_eof(handle)==0&&tar_close(handle)==0);
   string input="/backup/plain";
   if(compressed){
    string data=read_file(input);gzFile gz=gzopen("/backup/compressed","wb");CHECK(gz);
    CHECK(gzwrite(gz,data.data(),data.size())==static_cast<int>(data.size()));CHECK(gzclose(gz)==Z_OK);input="/backup/compressed";
   }
   if(encrypted)transform(true,input,out);else fs::copy_file(input,out,fs::copy_options::overwrite_existing);
  };
  const string archive="/backup/data.ext4.win";
  const string bad=symlink_case?(split?"/src/jump/keep":"jump/keep"):(split?"/outside/keep":"../outside/keep");
  if(split){volume(archive+"000","/src/good");volume(archive+(encrypted?"100":"001"),bad);}
  else volume(archive,bad);
  ProgressTracking progress(512);PartitionSettings settings;settings.progress=&progress;
  twrpTar restore;restore.setdir("/src");restore.setfn(archive);restore.setpassword("fixture-password");restore.part_settings=&settings;
  CHECK(restore.extractTarFork()!=0);CHECK(read_file("/outside/keep")=="DO NOT MODIFY");
  puts("PASS codec/volume selected-root rejection reaches parent; outside sentinel unchanged");return 0;
 }
 application_xattrs=scenario.find("-xattr")!=string::npos;
 directory_fixture=scenario.find("-dirtime")!=string::npos;
 bool compressed=scenario.find("gzip")!=string::npos||scenario.starts_with("both");
 bool encrypted=scenario.starts_with("aes")||scenario.starts_with("both")||scenario.starts_with("mixed");
 bool mixed=scenario.starts_with("mixed");
 bool entropy_fail=scenario.find("random-")!=string::npos;
 bool volume_limit=scenario.find("volume-limit")!=string::npos;
 bool split=scenario.find("split")!=string::npos||volume_limit;
 bool missing=scenario.find("missing-source")!=string::npos;
 bool empty=scenario.find("empty")!=string::npos;
 bool no_codec=scenario.find("no-codec")!=string::npos;
 security_fixture=scenario.find("-security-")!=string::npos;
 security_cap.magic_etc=VFS_CAP_REVISION_2|VFS_CAP_FLAGS_EFFECTIVE;
 security_cap.data[0].permitted=1U<<10;
 map<string,string> contents;
 string archive="/backup/data.ext4.win";
 if(scenario.find("percent")!=string::npos)archive="/backup/%s-data.ext4.win";
 fs::create_directory("/backup");
 if(!missing){fs::create_directory("/src");
  if(!empty){fs::create_directory("/src/dir");
   if(mixed){fs::create_directory("/src/app");write_file("/src/app/package","fixture-package");contents["app/package"]="fixture-package";chmod("/src/app/package",0640);}
   int count=volume_limit?105:(scenario=="aes-thread-gap"?1:12);
   for(int i=0;i<count;++i){string name="dir/file"+to_string(i);size_t n=split?48000:2000+i*17;string data(n,'\0');for(size_t j=0;j<n;++j)data[j]=(j*37+i*13)%251;
    write_file("/src/"+name,data);contents[name]=data;CHECK(chmod(("/src/"+name).c_str(),0640)==0);
   }
   CHECK(symlink("dir/file0","/src/link")==0);
   CHECK(setxattr("/src/dir","user.default","",0,0)==0);
   if(scenario.ends_with("-sparse")){
    string data(1048576+13,'\0');data[0]='A';data[524288]='B';
    int fd=open("/src/dir/sparse",O_CREAT|O_WRONLY,0640);CHECK(fd>=0);
    CHECK(ftruncate(fd,data.size())==0);
    CHECK(pwrite(fd,"A",1,0)==1);CHECK(pwrite(fd,"B",1,524288)==1);CHECK(close(fd)==0);
    contents["dir/sparse"]=data;
   }
  }
 }
 if(directory_fixture){
  fs::create_directory("/src/dir/nested");write_file("/src/dir/nested/payload","nested-content");
  contents["dir/nested/payload"]="nested-content";CHECK(chmod("/src/dir/nested/payload",0640)==0);
  const struct timespec times[2]={{root_time,0},{root_time,0}};
  const struct timespec child[2]={{child_time,0},{child_time,0}};
  CHECK(utimensat(AT_FDCWD,"/src",times,0)==0);
  CHECK(utimensat(AT_FDCWD,"/src/dir",child,0)==0);
  CHECK(utimensat(AT_FDCWD,"/src/dir/nested",child,0)==0);
  if(mixed)CHECK(utimensat(AT_FDCWD,"/src/app",child,0)==0);
 }
 if(application_xattrs){
  string blob(3000,'\0');for(size_t i=0;i<blob.size();++i)blob[i]=i%251;
  blob[1]=0;blob[2]='\n';blob[3]='=';
  CHECK(lsetxattr("/src/dir/file0","user.fixture_blob",blob.data(),blob.size(),0)==0);
  CHECK(lsetxattr("/src/dir/file0","user.fixture_empty","",0,0)==0);
  CHECK(lsetxattr("/src/dir","user.fixture_blob",blob.data(),blob.size(),0)==0);
 }
 if(no_codec)fs::remove("/bin/pigz");
 if(scenario=="aes-random-missing")fs::remove("/dev/urandom");
 if(scenario=="both-random-short")fs::resize_file("/dev/urandom",7);
 TWExclude exclude;uint64_t size=missing?12:exclude.Get_Folder_Size("/src");
 ProgressTracking progress(size);PartitionSettings settings;settings.progress=&progress;
 twrpTar tar;tar.setdir("/src");tar.setfn(archive);tar.setpassword("fixture-password");tar.setsize(size);
 tar.backup_folder="/backup";tar.partition_name="data";tar.part_settings=&settings;tar.backup_exclusions=&exclude;
 tar.use_compression=compressed;tar.use_encryption=encrypted;tar.userdata_encryption=mixed;
 if(application_xattrs&&scenario.ends_with("-read-error"))application_xattr_fault="read-error";
 BackupProcess process;int result=tar.createTarFork(&process);
 if(application_xattr_fault=="read-error"){CHECK(result!=0);CHECK(!fs::exists("/backup/data.info"));CHECK(read_file("/backup/security-calls").find("application-xattr-read-error")!=string::npos);puts("PASS application xattr read failure rejects backup publication");return 0;}
 if(missing||no_codec||entropy_fail||volume_limit){CHECK(result!=0);CHECK(!fs::exists("/backup/data.info"));puts("PASS expected backup failure");return 0;}
 CHECK(result==0);CHECK(fs::exists("/backup/data.info"));
 vector<fs::path> archives;for(auto& e:fs::directory_iterator("/backup"))if(e.path().filename().string().starts_with(fs::path(archive).filename().string()))archives.push_back(e.path());
 sort(archives.begin(),archives.end());CHECK(!archives.empty());if(split)CHECK(archives.size()>1);
 if(scenario=="aes-thread-gap"){
  CHECK(fs::exists("/backup/data.ext4.win100"));fs::rename("/backup/data.ext4.win000","/backup/full");
  fs::copy_file("/backup/data.ext4.win100","/backup/data.ext4.win000");fs::remove("/backup/data.ext4.win100");
  fs::remove("/backup/data.ext4.win200");fs::rename("/backup/full","/backup/data.ext4.win200");
 }
 bool corrupt=scenario.find("bad-crc")!=string::npos||scenario.find("truncated")!=string::npos||scenario.find("extra-invalid")!=string::npos;
 if(scenario.find("extra-invalid")!=string::npos){ofstream f(archives[0],ios::binary|ios::app);f<<string(64,'X');}
 if(scenario.find("bad-crc")!=string::npos){
  fs::path target=archives[0];if(encrypted){transform(false,target,"/backup/decrypted");target="/backup/decrypted";}
  string bytes=read_file(target);CHECK(bytes.size()>8);bytes[bytes.size()-8]^=0x5a;write_file(target,bytes);
  if(encrypted)transform(true,target,archives[0]);
 } else if(scenario.find("truncated")!=string::npos){
  auto n=fs::file_size(archives[0]);CHECK(n>7);fs::resize_file(archives[0],n-7);
 }
 fs::remove_all("/src");fs::create_directory("/src");
 twrpTar restore;restore.setdir("/src");restore.setfn(archive);restore.part_settings=&settings;
 bool wrong=scenario.find("wrong-password")!=string::npos;restore.setpassword(wrong?"incorrect":"fixture-password");
 if(directory_fixture){
  if(scenario.ends_with("-error"))directory_fault="error";
  if(scenario.ends_with("-symlink"))directory_fault="symlink";
  if(scenario.ends_with("-replace"))directory_fault="replace";
 }
 if(security_fixture)security_fault=scenario.substr(scenario.find("-security-")+10);
 if(application_xattrs&&scenario.ends_with("-write-error"))application_xattr_fault="write-error";
 result=restore.extractTarFork();
 if(application_xattrs){
  if(!application_xattr_fault.empty()){
   CHECK(result!=0);CHECK(read_file("/backup/security-calls").find("application-xattr-error")!=string::npos);
   puts("PASS application xattr failure reaches restore parent");return 0;
  }
  CHECK(result==0);
  string blob(3000,'\0');for(size_t i=0;i<blob.size();++i)blob[i]=i%251;
  blob[1]=0;blob[2]='\n';blob[3]='=';
  string got(3000,'\0');
  for(const char* path:{"/src/dir/file0","/src/dir"}){
   CHECK(lgetxattr(path,"user.fixture_blob",got.data(),got.size())==3000&&got==blob);
  }
  CHECK(lgetxattr("/src/dir/file0","user.fixture_empty",nullptr,0)==0);
  CHECK(lgetxattr("/src/dir/file1","user.fixture_blob",nullptr,0)==-1&&errno==ENODATA);
  puts("PASS application xattr binary/empty/directory/isolation through codec/workers");
 }
 if(directory_fixture){
  if(corrupt||wrong){CHECK(result!=0);CHECK(!fs::exists("/backup/security-calls"));puts("PASS invalid codec never finalizes directory times");return 0;}
  const auto calls=read_file("/backup/security-calls");
  CHECK(!calls.empty());
  if(!directory_fault.empty()){
   CHECK(result!=0);
   if(directory_fault!="error"){
    CHECK(calls.find("identity-replaced\n")!=string::npos);
    struct stat held{},changed{};CHECK(stat("/src/held",&held)==0&&held.st_mtime!=child_time);
    CHECK(lstat("/src/dir",&changed)==0);
    CHECK((directory_fault=="symlink")==static_cast<bool>(S_ISLNK(changed.st_mode)));
   }
   puts("PASS directory finalization failure reaches restore parent");return 0;
  }
  struct stat root{},dir{},nested{};CHECK(stat("/src",&root)==0&&stat("/src/dir",&dir)==0);
  CHECK(stat("/src/dir/nested",&nested)==0&&nested.st_mtime==child_time);
  CHECK(dir.st_mtime==child_time);
  if(mixed){struct stat app{};CHECK(stat("/src/app",&app)==0&&app.st_mtime==child_time);}
  printf("PASS archived directory times after all workers/codecs volumes=%zu root_unarchived=%ld child=%ld\n",archives.size(),root.st_mtime,dir.st_mtime);
 }
 if(security_fixture){
  const string calls=read_file("/backup/security-calls");
  CHECK(calls==(security_fault=="label-error"?"label\n":"label\ncap\n"));
  if(security_fault!="success"){
   CHECK(result!=0);CHECK(fs::exists("/src/dir/file0"));
   puts("PASS security metadata failure reaches extractTarFork; partial restore is retained");return 0;
  }
  char label[128];vfs_cap_data cap;
  CHECK(getxattr("/src/dir/file0","user.fixture_selinux",label,sizeof label)==sizeof security_context&&!strcmp(label,security_context));
  CHECK(getxattr("/src/dir/file0","user.fixture_capability",&cap,sizeof cap)==sizeof cap&&!memcmp(&cap,&security_cap,sizeof cap));
  puts("PASS security metadata arguments serialized/restored through codec and fork");
 }
 if(corrupt||wrong){CHECK(result!=0);puts("PASS expected restore failure");return 0;}
 CHECK(result==0);
 for(const auto& [name,data]:contents){CHECK(read_file("/src/"+name)==data);struct stat st{};CHECK(stat(("/src/"+name).c_str(),&st)==0);CHECK((st.st_mode&0777)==0640);}
 if(scenario.ends_with("-sparse")){
  struct stat st{};CHECK(stat("/src/dir/sparse",&st)==0);CHECK(st.st_size==1048576+13);
  CHECK(st.st_blocks*512<65536);printf("PASS codec sparse restored_blocks=%ld\n",st.st_blocks);
 }
 if(!contents.empty()){CHECK(fs::is_symlink("/src/link"));CHECK(fs::read_symlink("/src/link")=="dir/file0");char x[16]{};CHECK(getxattr("/src/dir","user.default",x,sizeof x)==0);}
 puts("PASS byte/mode/symlink/xattr roundtrip");return 0;
}
