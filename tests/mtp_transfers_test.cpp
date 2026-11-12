#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <thread>
#include <atomic>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sendfile.h>
#include <sys/syscall.h>
#include <cstdarg>
#include "mtp_objects_peer.hpp"
#include "twrp/TwrpMtpDatabase.hpp"
#include "MtpObjectInfo.h"
#include "MtpStringBuffer.h"
using namespace android;using namespace std;using namespace std::chrono_literals;
namespace fs=std::filesystem;
#define REQUIRE(x) do{if(!(x)){cerr<<"FAIL "<<__LINE__<<": "<<#x<<" errno="<<errno<<endl;_Exit(1);}}while(0)
atomic_int copy_fault=0, inotify_first=-1, inotify_second=-1;
atomic_bool force_exdev=false, fail_rename=false, drop_inotify=false, overflow_inotify=false;
atomic_int dropped_events=0;
extern "C" int __real_inotify_init();
extern "C" int __wrap_inotify_init(){int fd=__real_inotify_init();if(inotify_first==-1)inotify_first=fd;else inotify_second=fd;return fd;}
extern "C" ssize_t __real_read(int,void*,size_t);
extern "C" ssize_t __wrap_read(int fd,void* p,size_t n){
 auto got=__real_read(fd,p,n);
 if(got>0&&(fd==inotify_first||fd==inotify_second)){
  if(fd==inotify_first&&overflow_inotify.exchange(false)){inotify_event event{};event.wd=-1;event.mask=IN_Q_OVERFLOW;memcpy(p,&event,sizeof(event));return sizeof(event);}
  if(drop_inotify){++dropped_events;errno=EAGAIN;return -1;}
 }
 return got;
}
extern "C" long __real_syscall(long,...);
extern "C" long __wrap_syscall(long number,...){
 REQUIRE(number==__NR_renameat2);va_list args;va_start(args,number);int a=va_arg(args,int);auto* b=va_arg(args,const char*);int c=va_arg(args,int);auto* d=va_arg(args,const char*);unsigned e=va_arg(args,unsigned);va_end(args);
 if(force_exdev){errno=EXDEV;return -1;}if(fail_rename){errno=EACCES;return -1;}return __real_syscall(number,a,b,c,d,e);
}
extern "C" ssize_t __real_sendfile(int,int,off_t*,size_t);
extern "C" ssize_t __wrap_sendfile(int out,int in,off_t* offset,size_t count){
 if(copy_fault==1)count=min(count,size_t(2));
 if(copy_fault==2){copy_fault=0;errno=EINTR;return -1;}
 if(copy_fault==3)return 0;
 if(copy_fault==4){errno=ENOSPC;return -1;}
 return __real_sendfile(out,in,offset,count);
}
atomic_bool fail_mkdir=false;
extern "C" int __real_mkdir(const char*,mode_t);
extern "C" int __wrap_mkdir(const char* p,mode_t m){if(fail_mkdir&&string(p)=="/one/new-dir"){errno=EACCES;return -1;}return __real_mkdir(p,m);}
atomic_bool fail_partial=false;atomic_bool fail_unlink=false;atomic_int write_fault=0;
extern "C" int __real_unlinkat(int,const char*,int);
extern "C" int __wrap_unlinkat(int fd,const char* p,int flags){if(fail_unlink&&(!fail_partial||string(p)=="b.txt")){errno=EACCES;return -1;}return __real_unlinkat(fd,p,flags);}

bool upload_fd(int fd){struct stat a{},b{};return fstat(fd,&a)==0&&stat("/one/new.txt",&b)==0&&a.st_dev==b.st_dev&&a.st_ino==b.st_ino;}
extern "C" ssize_t __real_write(int,const void*,size_t);
extern "C" ssize_t __wrap_write(int fd,const void* p,size_t n){
 if(upload_fd(fd)){
  if(write_fault==1)n=min(n,size_t(7));
  if(write_fault==2){write_fault=0;errno=EINTR;return -1;}
  if(write_fault==4)return 0;
 }
 return __real_write(fd,p,n);
}
extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd){struct stat st{};if(copy_fault==6&&fstat(fd,&st)==0&&S_ISDIR(st.st_mode)){errno=EIO;return -1;}if(copy_fault==5||(write_fault==3&&upload_fd(fd))){errno=EIO;return -1;}return __real_fsync(fd);}
extern "C" int __real_close(int);
extern "C" int __wrap_close(int fd){
 struct stat a{},b{};bool fail=copy_fault==7&&fstat(fd,&a)==0&&stat("/two/a.txt",&b)==0&&a.st_dev==b.st_dev&&a.st_ino==b.st_ino;
 int result=__real_close(fd);if(fail){copy_fault=0;errno=EIO;return -1;}return result;
}
extern "C" int __real_unlink(const char*);
extern "C" int __wrap_unlink(const char* p){if(fail_unlink){errno=EACCES;return -1;}return __real_unlink(p);}
string readfile(const string& p){ifstream f(p,ios::binary);return {istreambuf_iterator<char>(f),{}};}
void writefile(const string& p,const string& data){ofstream f(p,ios::binary);f<<data;REQUIRE(f.good());}
template<class F> bool until(F f){for(int n=0;n<100;++n){if(f())return true;this_thread::sleep_for(10ms);}return false;}
Bytes words(initializer_list<uint32_t> xs){Bytes b;for(auto x:xs)put(b,x,4);return b;}
void str(Bytes& b,const string& s){b.push_back(s.size()+1);for(auto c:s)put(b,c,2);put(b,0,2);}
struct Reply{uint16_t code=0;Bytes response,data;};
struct Session {
 TwrpMtpDatabase db;unique_ptr<MtpServer> server;thread worker;uint32_t tx=0;
 Session(){server=make_unique<MtpServer>(&db,-1,false,"Fixture","dijun","1","test");}
 TwrpMtpStorage* add(uint32_t id,const string& path,uint64_t max_size=0){auto* s=new TwrpMtpStorage(id,path.c_str(),path.c_str(),false,max_size,server.get());server->addStorage(s);return s;}
 void start(){ {lock_guard l(peer.mutex);peer.disconnected=false;}worker=thread([&]{server->run();});}
 void stop(){ {lock_guard l(peer.mutex);peer.disconnected=true;peer.cv.notify_all();}if(worker.joinable())worker.join();}
 ~Session(){stop();/* database owns storages and must stop observers before server dies */}
 Reply call(uint16_t op,initializer_list<uint32_t> params={},const Bytes* data=nullptr){
  ++tx;unique_lock l(peer.mutex);auto first=peer.output.size();peer.input.push_back(packet(1,op,tx,words(params)));if(data)peer.input.push_back(packet(2,op,tx,*data));peer.cv.notify_all();
  REQUIRE(peer.cv.wait_for(l,2s,[&]{for(size_t i=first;i<peer.output.size();++i){auto& b=peer.output[i];if(b.size()>=12&&(word(b,4)&0xffff)==3&&word(b,8)==tx)return true;}return false;}));
  Reply result;for(size_t i=first;i<peer.output.size();++i){auto& b=peer.output[i];if(word(b,8)!=tx)continue;if((word(b,4)&0xffff)==3){result.code=word(b,4)>>16;result.response=b;}else result.data=b;}return result;
 }
 void open(){REQUIRE(call(MTP_OPERATION_OPEN_SESSION,{1}).code==MTP_RESPONSE_OK);}
};
uint32_t find(TwrpMtpDatabase& db,uint32_t store,const string& name,uint32_t parent=0xffffffff){
 unique_ptr<MtpObjectHandleList> ids(db.getObjectList(store,0,parent));for(auto id:*ids){MtpObjectInfo info(id);if(db.getObjectInfo(id,info)==MTP_RESPONSE_OK&&name==info.mName)return id;}return 0;
}
Bytes info(const string& name,uint32_t size,uint16_t format=MTP_FORMAT_UNDEFINED){
 Bytes b;put(b,0,4);put(b,format,2);put(b,0,2);put(b,size,4);put(b,0,2);
 for(int n=0;n<7;++n)put(b,0,4);put(b,0,2);put(b,0,4);put(b,0,4);str(b,name);str(b,"");str(b,"");str(b,"");return b;
}
int main(int argc,char** argv){
 REQUIRE(argc==2&&fs::exists(".fixture"));REQUIRE(chroot(".")==0&&chdir("/")==0);string test=argv[1];
 fs::create_directories("/one/dir/sub");fs::create_directories("/two");
 writefile("/one/a.txt","alpha");writefile("/one/dir/b.txt","bravo");writefile("/one/dir/sub/c.txt","charlie");writefile("/two/z.txt","zulu");
 if(test=="symlink-initial"){fs::create_symlink("/two/z.txt","/one/link");REQUIRE(mkfifo("/one/fifo",0600)==0);}
 // Delete server after the database: observer events hold its non-owning pointer.
 auto session=make_unique<Session>();auto& s=*session;
 auto* one=s.add(0x10001,"/one");s.add(0x20001,"/two");s.start();s.open();
 auto a=find(s.db,0x10001,"a.txt"),dir=find(s.db,0x10001,"dir");REQUIRE(a&&dir);
 if(test.rfind("rescan-",0)==0){
  drop_inotify=true;writefile("/one/a.txt","changed content");
  REQUIRE(until([&]{return dropped_events>0;}));
  if(test=="rescan-missing")fs::remove("/one/a.txt");
  s.db.rescanFile(test=="rescan-wrong-path"?"/two/z.txt":"/one/a.txt",a,MTP_FORMAT_UNDEFINED);
  if(test=="rescan-missing"){MtpObjectInfo object(a);REQUIRE(s.db.getObjectInfo(a,object)!=MTP_RESPONSE_OK);}
  else{TwrpMtpStorage::PropEntry property;REQUIRE(one->GetObjectPropertyValue(a,MTP_PROPERTY_OBJECT_SIZE,property)==0);REQUIRE(property.int_value==(test=="rescan-wrong-path"?5:15));}
 }else if(test.rfind("overflow-",0)==0){
  auto sub=find(s.db,0x10001,"sub",dir);auto child=find(s.db,0x10001,"c.txt",sub);REQUIRE(child);
  drop_inotify=true;
  fs::remove(test=="overflow-add-delete"?"/one/a.txt":"/one/dir/sub/c.txt");
  writefile(test=="overflow-add-delete"?"/one/new.txt":"/one/dir/sub/new.txt","new bytes");
  REQUIRE(until([&]{return dropped_events>0;}));this_thread::sleep_for(50ms);
  overflow_inotify=true;drop_inotify=false;writefile("/one/trigger","trigger");
  REQUIRE(until([&]{return !overflow_inotify;}));
  auto parent=test=="overflow-add-delete"?0xffffffff:sub;
  REQUIRE(until([&]{return find(s.db,0x10001,"new.txt",parent)!=0;}));
  MtpObjectInfo removed(test=="overflow-add-delete"?a:child);REQUIRE(s.db.getObjectInfo(removed.mHandle,removed)!=MTP_RESPONSE_OK);
  REQUIRE(find(s.db,0x10001,"dir")==dir);
 }else if(test=="root-removed"){
  fs::remove_all("/one");REQUIRE(until([&]{MtpObjectInfo object(a);return s.db.getObjectInfo(a,object)!=MTP_RESPONSE_OK;}));
  fs::create_directory("/one");writefile("/one/returned","alive");
  REQUIRE(until([&]{return find(s.db,0x10001,"returned")!=0;}));
 }else if(test=="parent-symlink-replacement"){
  fs::create_directory("/two/parent");fs::create_directory("/outside");
  REQUIRE(until([&]{return find(s.db,0x20001,"parent")!=0;}));auto parent=find(s.db,0x20001,"parent");
  drop_inotify=true;fs::rename("/two/parent","/two/old-parent");fs::create_symlink("/outside","/two/parent");
  auto r=s.call(MTP_OPERATION_COPY_OBJECT,{a,0x20001,parent});REQUIRE(r.code!=MTP_RESPONSE_OK);REQUIRE(!fs::exists("/outside/a.txt"));
 }else{
  bool copy=test.rfind("copy-",0)==0;
  bool folder=test.find("directory")!=string::npos||test.find("subtree-cycle")!=string::npos||test=="move-watch-after";
  uint32_t source=folder?dir:a,store=0x20001,parent=0;
  auto sub=find(s.db,0x10001,"sub",dir),child=find(s.db,0x10001,"c.txt",sub);REQUIRE(child);
  string name=folder?"dir":"a.txt",target="/two/"+name;
  if(test=="move-file"||test=="copy-within"){store=0x10001;parent=dir;target="/one/dir/a.txt";}
  if(test=="move-directory"){fs::create_directory("/one/target");REQUIRE(until([&]{return find(s.db,0x10001,"target")!=0;}));store=0x10001;parent=find(s.db,0x10001,"target");target="/one/target/dir";}
  if(test=="move-same-parent"){store=0x10001;target="/one/a.txt";}
  if(test.find("subtree-cycle")!=string::npos){store=0x10001;parent=sub;target="/one/dir/sub/dir";}
  if(test=="copy-invalid-parent")parent=0x12345678;
  if(test=="copy-parent-other-storage")parent=dir;
  if(test=="copy-invalid-storage")store=0x12345678;
  if(test=="copy-invalid-object")source=0x12345678;
  if(test=="copy-root")source=0;
  if(test.find("collision")!=string::npos){if(folder){fs::create_directory(target);writefile(target+"/keep","untouched");}else writefile(target,"untouched");}
  if(test=="copy-short-sendfile")copy_fault=1;
  if(test=="copy-eintr")copy_fault=2;
  if(test=="copy-zero-sendfile")copy_fault=3;
  if(test=="copy-enospc"||test=="copy-directory-enospc")copy_fault=4;
  if(test=="copy-fsync-fail")copy_fault=5;
  if(test=="copy-parent-fsync-fail")copy_fault=6;
  if(test=="copy-close-fail")copy_fault=7;
  if(test=="copy-directory-symlink")fs::create_symlink("/two/z.txt","/one/dir/link");
  if(test=="copy-directory-empty"){fs::remove_all("/one/dir/sub");fs::remove("/one/dir/b.txt");}

  if(test=="copy-symlink"||test=="copy-fifo"){
   fs::remove("/one/a.txt");if(test=="copy-symlink")fs::create_symlink("/two/z.txt","/one/a.txt");else REQUIRE(mkfifo("/one/a.txt",0600)==0);
  }
  if(test.find("max-size")!=string::npos){fs::create_directory("/small");s.add(0x30001,"/small",3);store=0x30001;target="/small/"+name;}
  force_exdev=test.find("cross-filesystem")!=string::npos||test.find("unlink-fail")!=string::npos||test=="move-cross-max-size";
  fail_partial=test=="move-directory-unlink-fail";fail_unlink=test.find("unlink-fail")!=string::npos;fail_rename=test=="move-rename-fail";
  bool good=test=="copy-file"||test=="copy-directory"||test=="copy-within"||test=="copy-short-sendfile"||test=="copy-eintr"||test=="move-file"||test=="move-directory"||test=="move-cross-storage"||test=="move-cross-filesystem"||test=="move-directory-cross-filesystem"||test=="move-same-parent"||test=="move-watch-after"||test=="copy-directory-empty"||test=="move-uid-stable";
  TwrpMtpStorage::PropEntry prior_uid;REQUIRE(one->GetObjectPropertyValue(a,MTP_PROPERTY_PERSISTENT_UID,prior_uid)==0);
  auto r=s.call(copy?MTP_OPERATION_COPY_OBJECT:MTP_OPERATION_MOVE_OBJECT,{source,store,parent});
  REQUIRE((r.code==MTP_RESPONSE_OK)==good);copy_fault=0;fail_unlink=false;force_exdev=false;
  if(good){
   if(test=="copy-directory-empty")REQUIRE(fs::is_empty(target));else if(folder)REQUIRE(readfile(target+"/sub/c.txt")=="charlie");else REQUIRE(readfile(target)=="alpha");
   uint32_t handle=copy?word(r.response,12):source;REQUIRE(copy?handle!=source:handle==source);
   MtpObjectInfo object(handle);REQUIRE(s.db.getObjectInfo(handle,object)==MTP_RESPONSE_OK);REQUIRE(object.mStorageID==store&&object.mParent==parent);
   if(copy)REQUIRE(fs::exists("/one/"+name));else if(test!="move-same-parent")REQUIRE(!fs::exists("/one/"+name));
   if(folder&&!copy){MtpObjectInfo moved(child);REQUIRE(s.db.getObjectInfo(child,moved)==MTP_RESPONSE_OK&&moved.mStorageID==store);}
   if(test=="move-watch-after"){writefile(target+"/sub/after","watch alive");REQUIRE(until([&]{return find(s.db,store,"after",sub)!=0;}));}
   REQUIRE(find(s.db,store,name,parent==0?0xffffffff:parent)==handle);
   if(test=="move-uid-stable"){
    writefile(target,"updated");auto* moved_store=static_cast<TwrpMtpStorage*>(s.server->getStorage(store));
    REQUIRE(until([&]{TwrpMtpStorage::PropEntry size;return moved_store->GetObjectPropertyValue(a,MTP_PROPERTY_OBJECT_SIZE,size)==0&&size.int_value==7;}));
    TwrpMtpStorage::PropEntry uid;REQUIRE(moved_store->GetObjectPropertyValue(a,MTP_PROPERTY_PERSISTENT_UID,uid)==0&&uid.int_value==prior_uid.int_value);
   }
  }else{
   if(test.find("collision")!=string::npos)REQUIRE(readfile(folder?target+"/keep":target)=="untouched");
   if(test.find("unlink-fail")!=string::npos){REQUIRE(readfile(folder?target+"/sub/c.txt":target)==(folder?"charlie":"alpha"));REQUIRE(find(s.db,store,name)!=0);}
   else if(test=="copy-parent-fsync-fail")REQUIRE(readfile(target)=="alpha");
   else if(test.find("collision")==string::npos)REQUIRE(!fs::exists(target));
   if(test=="move-directory-unlink-fail")REQUIRE(readfile("/one/dir/b.txt")=="bravo");
   else if(test!="copy-symlink"&&test!="copy-fifo")REQUIRE(readfile(folder?"/one/dir/sub/c.txt":"/one/a.txt")== (folder?"charlie":"alpha"));
  }
 }

 s.stop();
 // Storage lifetime is owned by db. Explicitly remove all storages from the
 // server list; database cleanup happens while the server remains alive below.
 auto server=std::move(s.server);session.reset();server.reset();
 cout<<"PASS "<<test<<endl;
}
