#include <algorithm>
#include <array>
#include <barrier>
#include <thread>
#include <mutex>
#include <cassert>
#include <cerrno>
#include <csignal>
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
#include <sys/wait.h>
#include <sys/xattr.h>
#include <unistd.h>
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
 bool compressed=scenario.find("gzip")!=string::npos||scenario.starts_with("both");
 bool encrypted=scenario.starts_with("aes")||scenario.starts_with("both")||scenario.starts_with("mixed");
 bool mixed=scenario.starts_with("mixed");
 bool entropy_fail=scenario.find("random-")!=string::npos;
 bool volume_limit=scenario.find("volume-limit")!=string::npos;
 bool split=scenario.find("split")!=string::npos||volume_limit;
 bool missing=scenario.find("missing-source")!=string::npos;
 bool empty=scenario.find("empty")!=string::npos;
 bool no_codec=scenario.find("no-codec")!=string::npos;
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
 if(no_codec)fs::remove("/bin/pigz");
 if(scenario=="aes-random-missing")fs::remove("/dev/urandom");
 if(scenario=="both-random-short")fs::resize_file("/dev/urandom",7);
 TWExclude exclude;uint64_t size=missing?12:exclude.Get_Folder_Size("/src");
 ProgressTracking progress(size);PartitionSettings settings;settings.progress=&progress;
 twrpTar tar;tar.setdir("/src");tar.setfn(archive);tar.setpassword("fixture-password");tar.setsize(size);
 tar.backup_folder="/backup";tar.partition_name="data";tar.part_settings=&settings;tar.backup_exclusions=&exclude;
 tar.use_compression=compressed;tar.use_encryption=encrypted;tar.userdata_encryption=mixed;
 BackupProcess process;int result=tar.createTarFork(&process);
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
 result=restore.extractTarFork();
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
