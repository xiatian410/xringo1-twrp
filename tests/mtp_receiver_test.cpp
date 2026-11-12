#include <cerrno>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
#include <sys/socket.h>
#include <unistd.h>
#include "MtpMessage.hpp"
#define MTPD(...) ((void)0)
#define MTPI(...) ((void)0)
#define MTPE(...) ((void)0)
static bool interrupt_once=false;
extern "C" ssize_t __real_recv(int,void*,size_t,int);
extern "C" ssize_t __real_read(int,void*,size_t);
extern "C" ssize_t __wrap_recv(int fd,void* p,size_t n,int f){if(interrupt_once){interrupt_once=false;errno=EINTR;return -1;}return __real_recv(fd,p,n,f);}
extern "C" ssize_t __wrap_read(int fd,void* p,size_t n){if(interrupt_once){interrupt_once=false;errno=EINTR;return -1;}return __real_read(fd,p,n);}
namespace android {
struct TwrpMtpStorage {unsigned id;std::string path,name;uint64_t max;TwrpMtpStorage(unsigned i,const char* p,const char* d,bool,uint64_t m,void*):id(i),path(p),name(d),max(m){}};
struct TwrpMtpServer {int mtp_read_pipe_=-1;std::vector<TwrpMtpStorage> added;std::vector<unsigned> removed;int MtpPipeThread();void addStorage(TwrpMtpStorage* s){added.push_back(*s);delete s;}void RemoveStorage(unsigned id){removed.push_back(id);}};
// PRODUCTION_METHOD
}
static void require(bool ok,const char* message){if(!ok){std::cerr<<"FAIL "<<message<<std::endl;exit(1);}}
int main(int argc,char** argv){require(argc==2,"argument");std::string which=argv[1];android::TwrpMtpServer server;
 if(which=="no-fd"){require(server.MtpPipeThread()==0,"no descriptor exits");return 0;}
 int pair[2];require(socketpair(AF_UNIX,SOCK_SEQPACKET,0,pair)==0,"fixture socket");server.mtp_read_pipe_=pair[0];MtpMessage msg{};msg.message_type=MTP_MESSAGE_ADD_STORAGE;msg.storage_id=1;strcpy(msg.path,"/fixture/media");strcpy(msg.display,"Internal");msg.max_file_size=123456;
 if(which=="remove")msg.message_type=MTP_MESSAGE_REMOVE_STORAGE;
 if(which=="zero-id")msg.storage_id=0;
 if(which=="unknown")msg.message_type=99;
 if(which=="bad-path")memset(msg.path,'p',sizeof(msg.path));
 if(which=="bad-display")memset(msg.display,'d',sizeof(msg.display));
 if(which=="eintr")interrupt_once=true;
 if(which!="eof"){
  std::vector<char> data(sizeof(msg)+(which=="oversized"?1:0));memcpy(data.data(),&msg,sizeof(msg));size_t count=which=="short"?7:data.size();require(send(pair[1],data.data(),count,MSG_NOSIGNAL)==ssize_t(count),"send fixture");
 }
 shutdown(pair[1],SHUT_WR);std::thread t([&]{server.MtpPipeThread();});t.join();close(pair[1]);
 bool add=which=="add"||which=="eintr";require(server.added.size()==size_t(add),"only valid complete add accepted");require(server.removed.size()==size_t(which=="remove"),"remove accepted once");if(add){const auto& s=server.added[0];require(s.id==1&&s.path=="/fixture/media"&&s.name=="Internal"&&s.max==123456,"storage fields preserved");}std::cout<<"PASS "<<which<<std::endl;
}
