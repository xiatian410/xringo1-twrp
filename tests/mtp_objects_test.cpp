#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <map>
#include <thread>
#include <atomic>
#include <fcntl.h>
#include <sys/stat.h>
#include "mtp_objects_peer.hpp"
#include "twrp/TwrpMtpDatabase.hpp"
#include "MtpObjectInfo.h"
#include "MtpStringBuffer.h"
using namespace android;using namespace std;using namespace std::chrono_literals;
namespace fs=std::filesystem;
#define REQUIRE(x) do{if(!(x)){cerr<<"FAIL "<<__LINE__<<": "<<#x<<" errno="<<errno<<endl;_Exit(1);}}while(0)
atomic_bool fail_mkdir=false;
extern "C" int __real_mkdir(const char*,mode_t);
extern "C" int __wrap_mkdir(const char* p,mode_t m){if(fail_mkdir&&string(p)=="/one/new-dir"){errno=EACCES;return -1;}return __real_mkdir(p,m);}
atomic_bool fail_unlink=false;atomic_int write_fault=0;
bool upload_fd(int fd);
atomic_int timestamp_calls=0;
atomic_bool timestamp_fault=false;
atomic_bool directory_timestamp_fault=false,directory_close_fault=false;
atomic_int directory_timestamp_calls=0;
atomic_bool directory_open_fault=false;
extern "C" int __real_open(const char*,int,...);
extern "C" int __wrap_open(const char*p,int flags,...){
 if(directory_open_fault&&string(p)=="/one/new-dir"&&(flags&O_DIRECTORY)){errno=EACCES;return -1;}
 if(flags&O_CREAT){va_list args;va_start(args,flags);auto mode=va_arg(args,int);va_end(args);return __real_open(p,flags,mode);}
 return __real_open(p,flags);
}
bool upload_directory(int fd){struct stat a{},b{};return fstat(fd,&a)==0&&S_ISDIR(a.st_mode)&&stat("/one/new-dir",&b)==0&&a.st_dev==b.st_dev&&a.st_ino==b.st_ino;}
extern "C" int __real_futimens(int,const struct timespec[2]);
extern "C" int __wrap_futimens(int fd,const struct timespec t[2]){
 if(upload_directory(fd)){++directory_timestamp_calls;if(directory_timestamp_fault){errno=EIO;return -1;}}
 if(upload_fd(fd)){++timestamp_calls;if(timestamp_fault){errno=EIO;return -1;}}
 return __real_futimens(fd,t);
}
atomic_int publish_fault=0;
extern "C" int __real_rename(const char*,const char*);
extern "C" int __wrap_rename(const char*a,const char*b){if(publish_fault==1&&string(a).find(".mtp-upload-")!=string::npos){errno=EIO;return -1;}return __real_rename(a,b);}
extern "C" int __real_mkstemp(char*);
extern "C" int __wrap_mkstemp(char*p){if(publish_fault==2){errno=ENOSPC;return -1;}return __real_mkstemp(p);}
extern "C" int __real_close(int);
extern "C" int __wrap_close(int fd){bool bad=(publish_fault==3&&upload_fd(fd))||(directory_close_fault&&upload_directory(fd));int r=__real_close(fd);if(bad){errno=EIO;return -1;}return r;}
extern "C" int __real_unlinkat(int,const char*,int);
extern "C" int __wrap_unlinkat(int fd,const char* p,int flags){if(fail_unlink){errno=EACCES;return -1;}return __real_unlinkat(fd,p,flags);}

bool upload_fd(int fd){
 struct stat a{},b{};if(fstat(fd,&a)!=0||!S_ISREG(a.st_mode))return false;
 for(const auto&e:fs::directory_iterator("/one")){
  auto n=e.path().filename().string();
  if(n!="new.txt"&&!n.starts_with(".mtp-upload-"))continue;
  if(stat(e.path().c_str(),&b)==0&&a.st_dev==b.st_dev&&a.st_ino==b.st_ino)return true;
 }return false;
}
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
extern "C" int __wrap_fsync(int fd){struct stat st{};if((write_fault==3&&upload_fd(fd))||(publish_fault==4&&fstat(fd,&st)==0&&S_ISDIR(st.st_mode))){errno=EIO;return -1;}return __real_fsync(fd);}
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
 TwrpMtpStorage* add(uint32_t id,const string& path){auto* s=new TwrpMtpStorage(id,path.c_str(),path.c_str(),false,0,server.get());server->addStorage(s);return s;}
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
Bytes info(const string& name,uint32_t size,uint16_t format=MTP_FORMAT_UNDEFINED,const string& modified=""){
 Bytes b;put(b,0,4);put(b,format,2);put(b,0,2);put(b,size,4);put(b,0,2);
 for(int n=0;n<7;++n)put(b,0,4);put(b,0,2);put(b,0,4);put(b,0,4);str(b,name);str(b,"");str(b,modified);str(b,"");return b;
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
 if(test.starts_with("staging-replaced-")){
  auto data=info("a.txt",3);
  REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data).code==MTP_RESPONSE_OK);
  write_fault=3;fail_unlink=true;Bytes partial{'b','a','d'};
  REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&partial).code!=MTP_RESPONSE_OK);
  fail_unlink=false;write_fault=0;
  string leftover;
  for(const auto& e:fs::directory_iterator("/one"))
   if(e.path().filename().string().starts_with(".mtp-upload-"))leftover=e.path();
  REQUIRE(!leftover.empty()&&readfile(leftover)=="bad"&&readfile("/one/a.txt")=="alpha");
  REQUIRE(find(s.db,0x10001,fs::path(leftover).filename())==0);
  // Keep the old inode allocated so replacement cannot accidentally reuse it.
  const int old=open(leftover.c_str(),O_RDONLY|O_CLOEXEC);REQUIRE(old>=0);
  struct stat before{},after{};REQUIRE(fstat(old,&before)==0);
  if(test.ends_with("modified"))this_thread::sleep_for(20ms);
  if(!test.ends_with("modified"))REQUIRE(unlink(leftover.c_str())==0);
  if(test.ends_with("directory"))fs::create_directory(leftover);
  else if(test.ends_with("symlink"))fs::create_symlink("/two/z.txt",leftover);
  else if(!test.ends_with("removed"))writefile(leftover,"user replacement");
  if(test.ends_with("modified")){
   REQUIRE(lstat(leftover.c_str(),&after)==0&&before.st_ino==after.st_ino);
   REQUIRE(before.st_ctim.tv_sec!=after.st_ctim.tv_sec||before.st_ctim.tv_nsec!=after.st_ctim.tv_nsec);
   cout<<"same_inode_ctime_changed=1 before="<<before.st_ctim.tv_sec<<":"<<before.st_ctim.tv_nsec
       <<" after="<<after.st_ctim.tv_sec<<":"<<after.st_ctim.tv_nsec<<endl;
  }
  if(test.ends_with("file")||test.ends_with("directory")||test.ends_with("modified")){
   REQUIRE(until([&]{return find(s.db,0x10001,fs::path(leftover).filename())!=0;}));
   REQUIRE(test.ends_with("directory")?fs::is_directory(leftover):readfile(leftover)=="user replacement");
  }else{
   REQUIRE(find(s.db,0x10001,fs::path(leftover).filename())==0);
   REQUIRE(test.ends_with("removed")?!fs::exists(leftover):fs::is_symlink(leftover));
   REQUIRE(readfile("/two/z.txt")=="zulu");
  }
  REQUIRE(close(old)==0);
  data=info("a.txt",3);
  REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data).code==MTP_RESPONSE_OK);
  Bytes retry{'n','e','w'};REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&retry).code==MTP_RESPONSE_OK);
  REQUIRE(readfile("/one/a.txt")=="new");
  cout<<"replaced_staging_identity_released=1 user_replacement_preserved=1 retry=1"<<endl;
 }else if(test=="staging-cleanup-retry"||test=="staging-cleanup-new"){
  const bool replacing=test=="staging-cleanup-retry";
  const string name=replacing?"a.txt":"new.txt",path="/one/"+name;
  const string user=".mtp-upload-user-owned";
  writefile("/one/"+user,"user data");
  REQUIRE(until([&]{return find(s.db,0x10001,user)!=0;}));
  map<string,string> leftovers;
  for(int round=0;round<2;++round){
   auto data=info(name,3);
   REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data).code==MTP_RESPONSE_OK);
   write_fault=3;fail_unlink=true;
   Bytes content(3,'N'+round);
   REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&content).code!=MTP_RESPONSE_OK);
   fail_unlink=false;write_fault=0;
   REQUIRE(replacing?readfile(path)=="alpha":!fs::exists(path));
   for(const auto& e:fs::directory_iterator("/one"))
    if(e.path().filename().string().starts_with(".mtp-upload-")&&e.path().filename()!=user)
     leftovers.try_emplace(e.path(),readfile(e.path()));
   REQUIRE(leftovers.size()==static_cast<size_t>(round+1));
   for(const auto&[p,bytes]:leftovers){
    REQUIRE(bytes.size()==3&&readfile(p)==bytes);
    REQUIRE(find(s.db,0x10001,fs::path(p).filename())==0);
   }
  }
  auto data=info(name,3);
  REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data).code==MTP_RESPONSE_OK);
  Bytes retry{'n','e','w'};
  REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&retry).code==MTP_RESPONSE_OK);
  REQUIRE(readfile(path)=="new");
  REQUIRE(replacing?find(s.db,0x10001,name)==a:find(s.db,0x10001,name)!=0);
  for(const auto&[p,bytes]:leftovers){
   REQUIRE(readfile(p)==bytes);
   REQUIRE(find(s.db,0x10001,fs::path(p).filename())==0);
  }
  REQUIRE(readfile("/one/"+user)=="user data"&&find(s.db,0x10001,user)!=0);
  cout<<"retry_after_two_cleanup_failures=1 hidden_orphans=2 user_prefix_visible=1"<<endl;
 }else if(test.starts_with("media-format-")){
  const vector<pair<string,uint16_t>> samples={
   {"note.txt",MTP_FORMAT_TEXT},{"index.HTML",MTP_FORMAT_HTML},{"index.htm",MTP_FORMAT_HTML},
   {"sound.WAV",MTP_FORMAT_WAV},{"song.mp3",MTP_FORMAT_MP3},{"movie.mpeg",MTP_FORMAT_MPEG},{"clip.mpg",MTP_FORMAT_MPEG},
   {"photo.JPG",MTP_FORMAT_EXIF_JPEG},{"photo.jpeg",MTP_FORMAT_EXIF_JPEG},{"scan.bmp",MTP_FORMAT_BMP},
   {"anim.gif",MTP_FORMAT_GIF},{"photo.jfif",MTP_FORMAT_JFIF},{"image.png",MTP_FORMAT_PNG},
   {"scan.tif",MTP_FORMAT_TIFF},{"scan.tiff",MTP_FORMAT_TIFF},{"song.wma",MTP_FORMAT_WMA},
   {"song.ogg",MTP_FORMAT_OGG},{"song.aac",MTP_FORMAT_AAC},{"clip.mp4",MTP_FORMAT_MP4_CONTAINER},
   {"song.mp2",MTP_FORMAT_MP2},{"clip.3gp",MTP_FORMAT_3GP_CONTAINER},{"clip.3gpp",MTP_FORMAT_3GP_CONTAINER},
   {"list.wpl",MTP_FORMAT_WPL_PLAYLIST},{"list.m3u",MTP_FORMAT_M3U_PLAYLIST},{"list.pls",MTP_FORMAT_PLS_PLAYLIST},
   {"data.xml",MTP_FORMAT_XML_DOCUMENT},{"song.flac",MTP_FORMAT_FLAC},
   {"noext",MTP_FORMAT_UNDEFINED},{".jpg",MTP_FORMAT_UNDEFINED},{"end.",MTP_FORMAT_UNDEFINED},
   {"image.jpg.zip",MTP_FORMAT_UNDEFINED},{"fake.jpgx",MTP_FORMAT_UNDEFINED},{"firmware.img",MTP_FORMAT_UNDEFINED}};
  auto check=[&](uint32_t h,const string& name,uint16_t expected){
   MtpObjectInfo entry(h);REQUIRE(s.db.getObjectInfo(h,entry)==MTP_RESPONSE_OK&&entry.mFormat==expected);
   TwrpMtpStorage::PropEntry prop;REQUIRE(one->GetObjectPropertyValue(h,MTP_PROPERTY_OBJECT_FORMAT,prop)==0&&prop.int_value==expected);
   MtpStringBuffer path;int64_t len=0;MtpObjectFormat format=0;
   REQUIRE(s.db.getObjectFilePath(h,path,len,format)==MTP_RESPONSE_OK&&format==expected);
   auto r=s.call(MTP_OPERATION_GET_OBJECT_INFO,{h});REQUIRE(r.code==MTP_RESPONSE_OK&&(word(r.data,16)&0xffff)==expected);
   r=s.call(MTP_OPERATION_GET_OBJECT_PROP_VALUE,{h,MTP_PROPERTY_OBJECT_FORMAT});REQUIRE(r.code==MTP_RESPONSE_OK&&(uint16_t(r.data.at(12))|(uint16_t(r.data.at(13))<<8))==expected);
   r=s.call(MTP_OPERATION_GET_OBJECT_HANDLES,{0x10001,expected,0});REQUIRE(r.code==MTP_RESPONSE_OK);
   bool found=false;for(size_t i=0;i<word(r.data,12);++i)found|=word(r.data,16+4*i)==h;REQUIRE(found);
   r=s.call(MTP_OPERATION_GET_OBJECT_PROP_LIST,{h,expected,MTP_PROPERTY_OBJECT_FORMAT,0,0});
   REQUIRE(r.code==MTP_RESPONSE_OK&&word(r.data,12)==1&&(uint16_t(r.data.at(24))|(uint16_t(r.data.at(25))<<8))==expected);
   const auto other=expected==MTP_FORMAT_MP3?MTP_FORMAT_PNG:MTP_FORMAT_MP3;
   r=s.call(MTP_OPERATION_GET_OBJECT_PROP_LIST,{h,static_cast<uint32_t>(other),MTP_PROPERTY_OBJECT_FORMAT,0,0});REQUIRE(r.code==MTP_RESPONSE_OK&&word(r.data,12)==0);
   REQUIRE(name==entry.mName);
  };
  if(test=="media-format-inventory"){
   for(const auto&[name,format]:samples){writefile("/one/"+name,"opaque bytes");REQUIRE(until([&]{return find(s.db,0x10001,name)!=0;}));check(find(s.db,0x10001,name),name,format);}
   fs::create_directory("/one/folder.mp3");REQUIRE(until([&]{return find(s.db,0x10001,"folder.mp3")!=0;}));check(find(s.db,0x10001,"folder.mp3"),"folder.mp3",MTP_FORMAT_ASSOCIATION);
  }else if(test=="media-format-rename"){
   Bytes data;str(data,"photo.JPG");REQUIRE(s.call(MTP_OPERATION_SET_OBJECT_PROP_VALUE,{a,MTP_PROPERTY_OBJECT_FILE_NAME},&data).code==MTP_RESPONSE_OK);check(a,"photo.JPG",MTP_FORMAT_EXIF_JPEG);
   data.clear();str(data,"opaque.bin");REQUIRE(s.call(MTP_OPERATION_SET_OBJECT_PROP_VALUE,{a,MTP_PROPERTY_OBJECT_FILE_NAME},&data).code==MTP_RESPONSE_OK);check(a,"opaque.bin",MTP_FORMAT_UNDEFINED);
  }else if(test=="media-format-upload"){
   auto data=info("new.PNG",3,MTP_FORMAT_UNDEFINED);auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);REQUIRE(r.code==MTP_RESPONSE_OK);auto h=word(r.response,20);
   Bytes payload{'a','b','c'};REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&payload).code==MTP_RESPONSE_OK);check(h,"new.PNG",MTP_FORMAT_PNG);
  }else if(test=="media-format-filter"){
   writefile("/one/dir/sub/nested.MP3","sound");REQUIRE(until([&]{return find(s.db,0x10001,"nested.MP3",0)!=0;}));
   auto r=s.call(MTP_OPERATION_GET_OBJECT_HANDLES,{0xffffffff,MTP_FORMAT_MP3,0});REQUIRE(r.code==MTP_RESPONSE_OK&&word(r.data,12)==1);
   r=s.call(MTP_OPERATION_GET_NUM_OBJECTS,{0xffffffff,MTP_FORMAT_MP3,0});REQUIRE(r.code==MTP_RESPONSE_OK&&word(r.response,12)==1);
  }else REQUIRE(false);
 }else if(test=="reset-disconnect"){
  {unique_lock l(peer.mutex);peer.reset_disconnect=true;peer.input.push_back({});peer.cv.notify_all();
   REQUIRE(peer.cv.wait_for(l,2s,[]{return peer.closes==1;}));
  }
 }else if(test.starts_with("reset-")){
  uint32_t reserved=0;
  if(test=="reset-pending-new"||test=="reset-pending-overwrite"||test=="reset-receive"){
   auto data=info(test=="reset-pending-overwrite"?"a.txt":"new.txt",60000);
   auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);
   REQUIRE(r.code==MTP_RESPONSE_OK);reserved=word(r.response,20);
  }
  if(test=="reset-edit")REQUIRE(s.call(MTP_OPERATION_BEGIN_EDIT_OBJECT,{a}).code==MTP_RESPONSE_OK);
  uint32_t interrupted=0;size_t first;
  {lock_guard l(peer.mutex);first=peer.output.size();
   if(test=="reset-data-in"){
    interrupted=++s.tx;peer.input.push_back(packet(1,MTP_OPERATION_SEND_OBJECT_INFO,interrupted,words({0x10001,0xffffffff})));peer.input.push_back({});
   }else if(test=="reset-data-out"||test=="reset-response"){
    peer.reset_next_write=true;interrupted=++s.tx;
    peer.input.push_back(packet(1,test=="reset-data-out"?MTP_OPERATION_GET_STORAGE_IDS:MTP_OPERATION_GET_NUM_OBJECTS,interrupted,words({0x10001,0,0xffffffff})));
   }else if(test=="reset-receive"){
    peer.reset_receive=true;interrupted=++s.tx;peer.input.push_back(packet(1,MTP_OPERATION_SEND_OBJECT,interrupted));peer.input.push_back(packet(2,MTP_OPERATION_SEND_OBJECT,interrupted,Bytes(60000,'N')));
   }else if(test=="reset-send"){
    peer.reset_send=true;interrupted=++s.tx;peer.input.push_back(packet(1,MTP_OPERATION_GET_OBJECT,interrupted,words({a})));
   }else peer.input.push_back({});
   peer.cv.notify_all();
  }
  // This following command is both a server-thread synchronization barrier
  // and a protocol assertion: class Reset requires a new OpenSession.
  REQUIRE(s.call(MTP_OPERATION_GET_STORAGE_IDS).code==MTP_RESPONSE_SESSION_NOT_OPEN);
  {lock_guard l(peer.mutex);REQUIRE(!peer.reset_pending);if(interrupted)for(size_t i=first;i<peer.output.size();++i)REQUIRE(word(peer.output[i],8)!=interrupted);}
  REQUIRE(readfile("/one/a.txt")=="alpha"&&!fs::exists("/one/new.txt"));
  for(const auto&e:fs::directory_iterator("/one"))REQUIRE(!e.path().filename().string().starts_with(".mtp-upload-"));
  if(reserved){MtpObjectInfo i(reserved);REQUIRE(test=="reset-pending-overwrite"?s.db.getObjectInfo(reserved,i)==MTP_RESPONSE_OK:s.db.getObjectInfo(reserved,i)!=MTP_RESPONSE_OK);}
  size_t events;{lock_guard l(peer.mutex);events=peer.events.size();}
  s.server->sendObjectAdded(a);{lock_guard l(peer.mutex);REQUIRE(peer.events.size()==events);}
  s.open();REQUIRE(s.call(MTP_OPERATION_GET_STORAGE_IDS).code==MTP_RESPONSE_OK);
  if(test=="reset-edit")REQUIRE(s.call(MTP_OPERATION_END_EDIT_OBJECT,{a}).code!=MTP_RESPONSE_OK);
  auto data=info("retry.txt",3);REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data).code==MTP_RESPONSE_OK);
  Bytes content{'o','k','!'};REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&content).code==MTP_RESPONSE_OK&&readfile("/one/retry.txt")=="ok!");
  {lock_guard l(peer.mutex);REQUIRE(peer.starts==1&&peer.closes==0);}
 }else if(test.starts_with("upload-time-")){
  setenv("TZ","CST-8",1);tzset();
  const bool replacing=test.starts_with("upload-time-overwrite-");
  const string kind=test.substr(replacing?22:16);
  const string name=replacing?"a.txt":"new.txt",path="/one/"+name;
  const bool missing=kind=="missing",invalid=kind=="invalid",failed=kind=="time-error"||kind=="receive-error"||kind=="sync-error";
  const string date=missing?"":invalid?"20260229T120000Z":kind=="epoch-offset"?"19700101T080000+0800":(kind=="pre-epoch"||kind=="receive-error")?"19691231T235959Z":"19700101T000000Z";
  const time_t expected=kind=="pre-epoch"?-1:0;
  if(replacing){timespec t[2]{{1234567,0},{1234567,0}};REQUIRE(utimensat(AT_FDCWD,path.c_str(),t,0)==0);}
  // Receive-error uses an entirely buffered payload, so a later request does
  // not assume an unimplemented endpoint drain after a partial bulk failure.
  const size_t size=kind=="receive-error"?3:60000;
  auto data=info(name,size,MTP_FORMAT_UNDEFINED,date);
  auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);REQUIRE(r.code==MTP_RESPONSE_OK);
  const auto handle=word(r.response,20);if(replacing)REQUIRE(handle==a);
  timestamp_fault=kind=="time-error";if(kind=="sync-error")write_fault=3;
  {lock_guard l(peer.mutex);peer.receive_fail=kind=="receive-error";}
  const auto before=time(nullptr);Bytes content(size,'T');r=s.call(MTP_OPERATION_SEND_OBJECT,{},&content);
  REQUIRE((r.code==MTP_RESPONSE_OK)==!failed);
  const int calls=timestamp_calls;timestamp_fault=false;write_fault=0;
  REQUIRE(calls==((missing||invalid||kind=="receive-error")?0:1));
  struct stat st{};
  if(failed){
   if(replacing)REQUIRE(stat(path.c_str(),&st)==0&&st.st_mtime==1234567&&readfile(path)=="alpha");
   else REQUIRE(!fs::exists(path));
  }else{
   REQUIRE(stat(path.c_str(),&st)==0&&readfile(path)==string(size,'T'));
   if(missing||invalid)REQUIRE(st.st_mtime>=before&&st.st_mtime<=time(nullptr));
   else REQUIRE(st.st_mtime==expected&&st.st_mtim.tv_nsec==0);
   MtpObjectInfo entry(handle);REQUIRE(s.db.getObjectInfo(handle,entry)==MTP_RESPONSE_OK&&entry.mDateModified==st.st_mtime);
  }
  for(const auto&e:fs::directory_iterator("/one"))REQUIRE(!e.path().filename().string().starts_with(".mtp-upload-"));
  // A subsequent upload without a date must use its own creation time, never
  // the previous transfer's valid epoch or a failed timestamp operation.
  auto retry=info("retry.txt",3);REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&retry).code==MTP_RESPONSE_OK);
  {lock_guard l(peer.mutex);peer.receive_fail=false;}
  Bytes payload{'o','k','!'};REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&payload).code==MTP_RESPONSE_OK);
  REQUIRE(stat("/one/retry.txt",&st)==0&&st.st_mtime>=before&&timestamp_calls==calls);
 }else if(test.starts_with("directory-time-")){
  setenv("TZ","CST-8",1);tzset();const auto kind=test.substr(15);
  const bool failed=kind=="time-error"||kind=="close-error"||kind=="open-error"||kind=="existing-time-error"||kind=="existing-close-error";
  const bool dated=kind!="missing"&&kind!="invalid"&&kind!="missing-unexpected-data";
  const string date=(kind=="missing"||kind=="missing-unexpected-data")?"":kind=="invalid"?"20260229T120000Z":kind=="offset"?"19700101T080000+0800":kind=="pre-epoch"?"19691231T235959Z":"19700101T000000Z";
  if(kind=="existing"||kind=="existing-time-error"||kind=="existing-close-error"){
   fs::create_directory("/one/new-dir");writefile("/one/new-dir/keep.txt","keep");
   auto initial=info("new-dir",0,MTP_FORMAT_ASSOCIATION);
   REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&initial).code==MTP_RESPONSE_OK);
  }
  directory_timestamp_fault=kind=="time-error"||kind=="existing-time-error";directory_close_fault=kind=="close-error"||kind=="existing-close-error";directory_open_fault=kind=="open-error";
  const auto before=time(nullptr);auto data=info("new-dir",0,MTP_FORMAT_ASSOCIATION,date);
  auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);
  REQUIRE((r.code==MTP_RESPONSE_OK)==!failed);
  directory_timestamp_fault=false;directory_close_fault=false;directory_open_fault=false;
  REQUIRE(fs::is_directory("/one/new-dir"));
  struct stat st{};REQUIRE(stat("/one/new-dir",&st)==0);
  REQUIRE(directory_timestamp_calls==((dated&&kind!="open-error")?1:0));
  const auto actual_handle=find(s.db,0x10001,"new-dir");REQUIRE(actual_handle);
  MtpObjectInfo actual(actual_handle);REQUIRE(s.db.getObjectInfo(actual_handle,actual)==MTP_RESPONSE_OK&&actual.mDateModified==st.st_mtime);
  if(!failed){
   if(dated)REQUIRE(st.st_mtime==(kind=="pre-epoch"?-1:0)&&st.st_mtim.tv_nsec==0);
   else REQUIRE(st.st_mtime>=before&&st.st_mtime<=time(nullptr));
   const auto h=word(r.response,20);MtpObjectInfo entry(h);REQUIRE(s.db.getObjectInfo(h,entry)==MTP_RESPONSE_OK&&entry.mDateModified==st.st_mtime);
   if(kind=="existing")REQUIRE(readfile("/one/new-dir/keep.txt")=="keep");
  }
  // A directory finishes in SendObjectInfo, and must not reserve a later
  // SendObject. Use an empty data packet to keep the pre-fix peer synchronized.
  if(kind=="existing-time-error"||kind=="existing-close-error")REQUIRE(readfile("/one/new-dir/keep.txt")=="keep");
  if(kind=="unexpected-data"||kind=="missing-unexpected-data"||failed){Bytes empty;REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&empty).code==MTP_RESPONSE_NO_VALID_OBJECT_INFO);}
  if(kind=="next-command")REQUIRE(s.call(MTP_OPERATION_GET_STORAGE_IDS).code==MTP_RESPONSE_OK);
  if(kind=="retry"||failed){
   data=info("new-dir",0,MTP_FORMAT_ASSOCIATION,"19691231T235959Z");
   REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data).code==MTP_RESPONSE_OK);
   REQUIRE(stat("/one/new-dir",&st)==0&&st.st_mtime==-1);
  }
  data=info("retry.txt",3);REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data).code==MTP_RESPONSE_OK);
  Bytes payload{'o','k','!'};REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&payload).code==MTP_RESPONSE_OK);
  REQUIRE(stat("/one/retry.txt",&st)==0&&st.st_mtime>=before&&readfile("/one/retry.txt")=="ok!");
 }else if(test.starts_with("atomic-")){
  const bool replacing=!test.starts_with("atomic-new-");
  const string name=replacing?"a.txt":"new.txt",path="/one/"+name;
  const auto oldid=replacing?a:0;const string old=replacing?"alpha":"";
  const bool good=test=="atomic-overwrite-success"||test=="atomic-new-success"||test.ends_with("directory-sync");
  write_fault=test.ends_with("sync-error")?3:test.ends_with("write-error")?4:0;
  publish_fault=test.ends_with("rename-error")?1:test.ends_with("create-error")?2:test.ends_with("close-error")?3:test.ends_with("directory-sync")?4:0;
  bool observed=false;
  receiving_probe=[&](int){
   observed=true;
   REQUIRE(replacing?readfile(path)==old:!fs::exists(path));
   if(test.ends_with("process-death"))_Exit(42);
   this_thread::sleep_for(30ms);
   if(replacing)REQUIRE(find(s.db,0x10001,name)==oldid);
   for(const auto&e:fs::directory_iterator("/one"))if(e.path().filename().string().starts_with(".mtp-upload-"))REQUIRE(find(s.db,0x10001,e.path().filename())==0);
  };
  auto data=info(name,60000);auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);REQUIRE(r.code==MTP_RESPONSE_OK);
  const auto handle=word(r.response,20);if(replacing)REQUIRE(handle==oldid);
  {lock_guard l(peer.mutex);peer.receive_fail=test.ends_with("receive-error");peer.receive_cancel=test.ends_with("cancel");peer.receive_short_success=test.ends_with("short-error");}
  Bytes content(60000,'N');
  if(test.ends_with("cancel")){
   uint32_t cancelled;size_t first;
   {lock_guard l(peer.mutex);cancelled=++s.tx;first=peer.output.size();peer.input.push_back(packet(1,MTP_OPERATION_SEND_OBJECT,cancelled));peer.input.push_back(packet(2,MTP_OPERATION_SEND_OBJECT,cancelled,content));peer.cv.notify_all();}
   // Cancel responses are deliberately suppressed by MtpServer. A following
   // request is the synchronization barrier, as on the real cancel path.
   REQUIRE(s.call(MTP_OPERATION_GET_STORAGE_IDS).code==MTP_RESPONSE_OK);
   {lock_guard l(peer.mutex);for(size_t i=first;i<peer.output.size();++i)REQUIRE(word(peer.output[i],8)!=cancelled);}
   r.code=MTP_RESPONSE_TRANSACTION_CANCELLED;
  }else r=s.call(MTP_OPERATION_SEND_OBJECT,{},&content);
  REQUIRE((r.code==MTP_RESPONSE_OK)==good);
  if(test.ends_with("cancel"))REQUIRE(r.code==MTP_RESPONSE_TRANSACTION_CANCELLED);
  if(good)REQUIRE(readfile(path)==string(60000,'N'));
  else REQUIRE(replacing?readfile(path)==old:!fs::exists(path));
  if(!test.ends_with("create-error")&&!test.ends_with("write-error"))REQUIRE(observed);
  receiving_probe={};write_fault=0;publish_fault=0;
  this_thread::sleep_for(60ms);
  for(const auto&e:fs::directory_iterator("/one"))REQUIRE(!e.path().filename().string().starts_with(".mtp-upload-"));
  if(replacing)REQUIRE(find(s.db,0x10001,name)==oldid);
  else REQUIRE((find(s.db,0x10001,name)!=0)==good);
 }else if(test=="enumerate-root"||test=="enumerate-recursive"||test=="enumerate-all-storages"){
  uint32_t store=test=="enumerate-all-storages"?0xffffffff:0x10001;uint32_t parent=test=="enumerate-recursive"?0:0xffffffff;
  auto r=s.call(MTP_OPERATION_GET_OBJECT_HANDLES,{store,0,parent});REQUIRE(r.code==MTP_RESPONSE_OK);REQUIRE(word(r.data,12)==(test=="enumerate-root"?2:test=="enumerate-recursive"?5:3));
 }else if(test=="count-all-storages"){
  auto r=s.call(MTP_OPERATION_GET_NUM_OBJECTS,{0xffffffff,0,0xffffffff});REQUIRE(r.code==MTP_RESPONSE_OK);REQUIRE(word(r.response,12)==3);
 }else if(test=="property-recursive"){
  auto r=s.call(MTP_OPERATION_GET_OBJECT_PROP_LIST,{0xffffffff,0,MTP_PROPERTY_OBJECT_FILE_NAME,0,0});REQUIRE(r.code==MTP_RESPONSE_OK);REQUIRE(word(r.data,12)==6);
 }else if(test=="upload-date-east"||test=="upload-date-west"||test=="upload-date-fraction"||test=="upload-date-invalid"){
  setenv("TZ","CST-8",1);tzset();
  string date=test=="upload-date-east"?"20261111T020953+0800":test=="upload-date-west"?"20261110T100953-0800":test=="upload-date-fraction"?"20261110T180953.5Z":"20260229T120000Z";
  auto data=info("dated.txt",3,MTP_FORMAT_UNDEFINED,date);auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);REQUIRE(r.code==MTP_RESPONSE_OK);
  auto before=time(nullptr);Bytes content{'a','b','c'};REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&content).code==MTP_RESPONSE_OK);
  struct stat st{};REQUIRE(stat("/one/dated.txt",&st)==0&&readfile("/one/dated.txt")=="abc");
  if(test=="upload-date-invalid")REQUIRE(st.st_mtime>=before&&st.st_mtime<=time(nullptr));
  else REQUIRE(st.st_mtime==1794334193);
 }else if(test=="upload-download"||test=="upload-abandoned"||test=="upload-failed"){
  auto data=info("new.txt",11);auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);REQUIRE(r.code==MTP_RESPONSE_OK);auto handle=word(r.response,20);
  if(test=="upload-abandoned"){s.call(MTP_OPERATION_GET_STORAGE_IDS);MtpObjectInfo i(handle);REQUIRE(s.db.getObjectInfo(handle,i)!=MTP_RESPONSE_OK);}
  else {Bytes content{'h','e','l','l','o',' ','w','o','r','l','d'};{lock_guard l(peer.mutex);peer.receive_fail=test=="upload-failed";}r=s.call(MTP_OPERATION_SEND_OBJECT,{},&content);
   if(test=="upload-failed"){REQUIRE(r.code!=MTP_RESPONSE_OK);REQUIRE(!fs::exists("/one/new.txt"));}
   else {REQUIRE(r.code==MTP_RESPONSE_OK);REQUIRE(readfile("/one/new.txt")=="hello world");r=s.call(MTP_OPERATION_GET_OBJECT,{handle});REQUIRE(r.code==MTP_RESPONSE_OK);REQUIRE(string(r.data.begin()+12,r.data.end())=="hello world");}
  }
 }else if(test=="delete-success"||test=="delete-failed"){
  fail_unlink=test=="delete-failed";auto r=s.call(MTP_OPERATION_DELETE_OBJECT,{a,0});REQUIRE((r.code==MTP_RESPONSE_OK)==!fail_unlink);MtpObjectInfo i(a);REQUIRE((s.db.getObjectInfo(a,i)==MTP_RESPONSE_OK)==bool(fail_unlink));REQUIRE(fs::exists("/one/a.txt")==bool(fail_unlink));fail_unlink=false;
 }else if(test=="rename-success"||test=="rename-collision"||test=="rename-dot-name"){
  string name=test=="rename-success"?"renamed.txt":test=="rename-collision"?"target.txt":"..";
  if(test=="rename-collision")writefile("/one/target.txt","keep");Bytes data;str(data,name);auto r=s.call(MTP_OPERATION_SET_OBJECT_PROP_VALUE,{a,MTP_PROPERTY_OBJECT_FILE_NAME},&data);
  REQUIRE((r.code==MTP_RESPONSE_OK)==(test=="rename-success"));if(test=="rename-success")REQUIRE(readfile("/one/renamed.txt")=="alpha");else REQUIRE(readfile("/one/a.txt")=="alpha");if(test=="rename-collision")REQUIRE(readfile("/one/target.txt")=="keep");
 }else if(test=="storage-remove"||test=="storage-readd"||test=="empty-storage"){
  s.server->removeStorage(one);MtpObjectInfo i(a);REQUIRE(s.db.getObjectInfo(a,i)!=MTP_RESPONSE_OK);
  if(test=="storage-readd"){s.add(0x10001,"/one");REQUIRE(find(s.db,0x10001,"a.txt")!=a);}
  if(test=="empty-storage"){s.server->removeStorage(s.server->getStorage(0x20001));REQUIRE(s.server->getStorage(0)==nullptr);}
 }else if(test=="reconnect-session"){
  s.stop();s.start();REQUIRE(s.call(MTP_OPERATION_OPEN_SESSION,{2}).code==MTP_RESPONSE_OK);
 }else if(test=="external-create-delete"){
  writefile("/one/external.txt","x");REQUIRE(until([&]{return find(s.db,0x10001,"external.txt")!=0;}));auto h=find(s.db,0x10001,"external.txt");fs::remove("/one/external.txt");REQUIRE(until([&]{MtpObjectInfo i(h);return s.db.getObjectInfo(h,i)!=MTP_RESPONSE_OK;}));
 }else if(test=="external-modify"){
  writefile("/one/a.txt","longer alpha");REQUIRE(until([&]{TwrpMtpStorage::PropEntry e;return one->GetObjectPropertyValue(a,MTP_PROPERTY_OBJECT_SIZE,e)==0&&e.int_value==12;}));
 }else if(test=="external-subtree-delete"){
  auto sub=find(s.db,0x10001,"sub",dir);auto child=find(s.db,0x10001,"c.txt",sub);REQUIRE(child);fs::remove_all("/one/dir");REQUIRE(until([&]{MtpObjectInfo i(child);return s.db.getObjectInfo(child,i)!=MTP_RESPONSE_OK;}));
 }else if(test=="directory-upload"){
  auto data=info("new-dir",0,MTP_FORMAT_ASSOCIATION);auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);REQUIRE(r.code==MTP_RESPONSE_OK);auto handle=word(r.response,20);REQUIRE(fs::is_directory("/one/new-dir"));
  data=info("inside",3);r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,handle},&data);REQUIRE(r.code==MTP_RESPONSE_OK);Bytes content{'a','b','c'};REQUIRE(s.call(MTP_OPERATION_SEND_OBJECT,{},&content).code==MTP_RESPONSE_OK);REQUIRE(readfile("/one/new-dir/inside")=="abc");
 }else if(test=="disconnect-pending"){
  auto data=info("abandoned",100);auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);REQUIRE(r.code==MTP_RESPONSE_OK);auto h=word(r.response,20);s.stop();MtpObjectInfo i(h);REQUIRE(s.db.getObjectInfo(h,i)!=MTP_RESPONSE_OK);s.start();s.open();
 }else if(test=="duplicate-storage"){
  s.add(0x10001,"/two");REQUIRE(find(s.db,0x10001,"a.txt")==a);auto r=s.call(MTP_OPERATION_GET_STORAGE_IDS);REQUIRE(r.code==MTP_RESPONSE_OK&&word(r.data,12)==2);
 }else if(test=="missing-root"){
  s.add(0x30001,"/missing");auto r=s.call(MTP_OPERATION_GET_STORAGE_IDS);REQUIRE(r.code==MTP_RESPONSE_OK&&word(r.data,12)==2);REQUIRE(s.server->getStorage(0x30001)==nullptr);
 }else if(test=="format-filter"){
  auto r=s.call(MTP_OPERATION_GET_OBJECT_HANDLES,{0xffffffff,MTP_FORMAT_ASSOCIATION,0});REQUIRE(r.code==MTP_RESPONSE_OK&&word(r.data,12)==2);
 }else if(test=="upload-too-long"||test=="upload-short-success"||test=="upload-large"||test=="upload-short-write"||test=="upload-eintr"||test=="upload-sync-fail"||test=="upload-zero-write"){
  bool good=test=="upload-large"||test=="upload-short-write"||test=="upload-eintr";
  write_fault=test=="upload-short-write"?1:test=="upload-eintr"?2:test=="upload-sync-fail"?3:test=="upload-zero-write"?4:0;
  uint32_t declared=good?60000:10;Bytes content(good?60000:test=="upload-too-long"?11:test=="upload-short-success"?7:10,'V');
  auto data=info("new.txt",declared);auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);REQUIRE(r.code==MTP_RESPONSE_OK);
  {lock_guard l(peer.mutex);peer.receive_short_success=test=="upload-short-success";}
  r=s.call(MTP_OPERATION_SEND_OBJECT,{},&content);REQUIRE((r.code==MTP_RESPONSE_OK)==good);
  if(good)REQUIRE(readfile("/one/new.txt")==string(60000,'V'));else REQUIRE(!fs::exists("/one/new.txt"));
 }else if(test=="events-concurrent"){
  {lock_guard l(peer.mutex);peer.events.clear();}
  vector<thread> threads;for(int n=0;n<6;++n)threads.emplace_back([&,n]{for(int i=0;i<500;++i)s.server->sendObjectAdded(10000+n*500+i);});for(auto& t:threads)t.join();
  lock_guard l(peer.mutex);set<uint32_t> handles;REQUIRE(peer.events.size()==3000);for(auto& e:peer.events){REQUIRE((word(e,4)>>16)==MTP_EVENT_OBJECT_ADDED);handles.insert(word(e,12));}REQUIRE(handles.size()==3000&&*handles.begin()==10000&&*handles.rbegin()==12999);
 }else if(test=="symlink-hidden"){
  fs::create_symlink("/two/z.txt","/one/link");this_thread::sleep_for(100ms);REQUIRE(find(s.db,0x10001,"link")==0);
 }else if(test=="directory-upload-fail"){
  fail_mkdir=true;auto data=info("new-dir",0,MTP_FORMAT_ASSOCIATION);auto r=s.call(MTP_OPERATION_SEND_OBJECT_INFO,{0x10001,0xffffffff},&data);REQUIRE(r.code!=MTP_RESPONSE_OK);REQUIRE(find(s.db,0x10001,"new-dir")==0);fail_mkdir=false;
 }else if(test=="rename-root"){
  REQUIRE(one->RenameObject(0,"moved")!=0);REQUIRE(fs::is_directory("/one"));
 }else if(test=="symlink-initial"){
  REQUIRE(find(s.db,0x10001,"link")==0&&find(s.db,0x10001,"fifo")==0);
 }else if(test=="property-format-filter"||test=="property-depth-one"){
  uint32_t handle=test=="property-format-filter"?0xffffffff:dir;uint32_t format=test=="property-format-filter"?MTP_FORMAT_ASSOCIATION:0;
  auto r=s.call(MTP_OPERATION_GET_OBJECT_PROP_LIST,{handle,format,MTP_PROPERTY_OBJECT_FILE_NAME,0,test=="property-depth-one"?1U:0U});REQUIRE(r.code==MTP_RESPONSE_OK);REQUIRE(word(r.data,12)==(test=="property-format-filter"?2:3));
 }else if(test=="send-parent-mismatch"||test=="send-dot-name"){
  auto h=one->BeginSendObject(test=="send-parent-mismatch"?"/two/escape":"/one/..",MTP_FORMAT_UNDEFINED,0,0,0);REQUIRE(h==kInvalidObjectHandle);
 }else if(test=="partial-beyond-eof"){
  auto r=s.call(MTP_OPERATION_GET_PARTIAL_OBJECT,{a,100,20});REQUIRE(r.code==MTP_RESPONSE_INVALID_PARAMETER || (r.code==MTP_RESPONSE_OK&&word(r.response,12)==0));
 }else REQUIRE(false);
 s.stop();
 {
  lock_guard l(peer.mutex);
  REQUIRE(!peer.transaction_lifetime_error&&peer.active_transaction==0);
  REQUIRE(!peer.transaction_lifetimes.empty()&&peer.transaction_lifetimes.size()%2==0);
  for(size_t i=0;i<peer.transaction_lifetimes.size();i+=2){
   REQUIRE(peer.transaction_lifetimes[i]>>32==1);
   REQUIRE(peer.transaction_lifetimes[i+1]==0);
  }
 }
 // Storage lifetime is owned by db. Explicitly remove all storages from the
 // server list; database cleanup happens while the server remains alive below.
 auto server=std::move(s.server);session.reset();server.reset();
 cout<<"PASS "<<test<<endl;
}
