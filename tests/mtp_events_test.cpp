#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdarg>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <mutex>
#include <set>
#include <thread>
#include <unistd.h>
#include <asyncio/AsyncIO.h>
#include "MtpFfsHandle.h"
#include "MtpFfsCompatHandle.h"
using namespace std::chrono_literals;
static std::atomic<int> event_fd{-1}, fault{0}, submits{0}, cancels{0};
static std::mutex aio_mutex;
static aio_context_t pending_ctx=0;
static iocb* pending=nullptr;
static void require(bool b,const char* s){if(!b){std::cerr<<"FAIL: "<<s<<std::endl;std::_Exit(1);}}
extern "C" int __real_io_submit(aio_context_t,long,iocb**);
extern "C" int __real_io_getevents(aio_context_t,long,long,io_event*,timespec*);
extern "C" int __real_io_cancel(aio_context_t,iocb*,io_event*);
extern "C" int __real_io_destroy(aio_context_t);
extern "C" int __real_io_setup(unsigned,aio_context_t*);
extern "C" int __real_fcntl(int,int,...);
extern "C" int __wrap_fcntl(int fd,int cmd,...){
    if(cmd==F_GETFL){if(fd==event_fd&&fault==8){errno=EBADF;return -1;}return __real_fcntl(fd,cmd);}
    va_list a;va_start(a,cmd);int val=va_arg(a,int);va_end(a);return __real_fcntl(fd,cmd,val);
}
extern "C" int __wrap_io_setup(unsigned n,aio_context_t* c){if(n==1&&fault==7){errno=EAGAIN;return -1;}return __real_io_setup(n,c);}
extern "C" int __wrap_io_submit(aio_context_t c,long n,iocb** p){
    if(n==1&&int(p[0]->aio_fildes)==event_fd){
        int count=++submits;
        if((fault==1||fault==2)&&count<=3){errno=fault==1?EINTR:EAGAIN;return -1;}
        if(fault==3){errno=EIO;return -1;}
        if(fault==4||fault==5||fault==6||fault==9||fault==10||fault==11||((fault==12||fault==13)&&count<=3)){std::lock_guard<std::mutex> l(aio_mutex);pending_ctx=c;pending=p[0];return 1;}
    }
    return __real_io_submit(c,n,p);
}
extern "C" int __wrap_io_getevents(aio_context_t c,long lo,long hi,io_event* e,timespec* t){
    std::lock_guard<std::mutex> l(aio_mutex);
    if(c==pending_ctx&&pending){
        if(fault==6||fault==9||fault==10||fault==11)return 0;
        *e={};e->obj=reinterpret_cast<uint64_t>(pending);e->res=fault==4?pending->aio_nbytes-1:fault==12?-EINTR:fault==13?-EAGAIN:-EIO;pending=nullptr;return 1;
    }
    return __real_io_getevents(c,lo,hi,e,t);
}
extern "C" int __wrap_io_cancel(aio_context_t c,iocb* p,io_event* e){
    std::lock_guard<std::mutex> l(aio_mutex);++cancels;
    if(c==pending_ctx&&p==pending){*e={};e->obj=reinterpret_cast<uint64_t>(p);e->res=-ECANCELED;pending=nullptr;if(fault==9||fault==10){errno=fault==9?EINPROGRESS:EINVAL;return -1;}return 0;}
    return __real_io_cancel(c,p,e);
}
extern "C" int __wrap_io_destroy(aio_context_t c){
    {std::lock_guard<std::mutex> l(aio_mutex);if(c==pending_ctx){require(!pending,"request canceled before destroying context");pending_ctx=0;}}
    return __real_io_destroy(c);
}
static std::vector<unsigned char> packet(unsigned n){std::vector<unsigned char> p(16,0);p[0]=16;memcpy(p.data()+4,&n,4);return p;}
namespace android {
template<class T> class MtpFfsHandleTest {
public:
    T handle{-1};
    base::unique_fd control,bin,bout,intr;
    MtpFfsHandleTest(){attach();}
    void attach(){int f[2];require(pipe(f)==0,"control pipe");control.reset(f[0]);handle.mControl.reset(f[1]);require(pipe(f)==0,"bulk in pipe");bin.reset(f[0]);handle.mBulkIn.reset(f[1]);require(pipe(f)==0,"bulk out pipe");bout.reset(f[1]);handle.mBulkOut.reset(f[0]);require(pipe(f)==0,"interrupt pipe");intr.reset(f[0]);handle.mIntr.reset(f[1]);event_fd=f[1];}
    void start(){require(handle.start(false)==0,"start");}
    int send(unsigned i){auto p=packet(i);return handle.sendEvent({p.size(),p.data()});}
    size_t fill(){size_t total=0;int fd=handle.mIntr.get(),flags=fcntl(fd,F_GETFL);fcntl(fd,F_SETFL,flags|O_NONBLOCK);char p[4096]={};while(::write(fd,p,sizeof(p))>0){total+=sizeof(p);}require(errno==EAGAIN,"pipe full");fcntl(fd,F_SETFL,flags);return total;}
    std::vector<unsigned char> readBytes(size_t n){std::vector<unsigned char> out(n);size_t done=0;auto until=std::chrono::steady_clock::now()+2s;while(done<n&&std::chrono::steady_clock::now()<until){pollfd p{intr.get(),POLLIN,0};if(poll(&p,1,20)>0){auto r=::read(intr,out.data()+done,n-done);if(r>0)done+=r;}}require(done==n,"complete event bytes before deadline");return out;}
    void close(){auto t=std::chrono::steady_clock::now();handle.close();require(std::chrono::steady_clock::now()-t<1s,"close bounded");require(base::GetProperty("sys.usb.ffs.mtp.ready","")=="0","close clears readiness");}
};
}
template<class T> void run(const std::string& c){
    auto t=std::make_unique<android::MtpFfsHandleTest<T>>();
    if(c=="before-start"){require(t->send(1)==-1,"reject before start");return;}
    if(c=="setup-error"||c=="fcntl-error"){fault=c=="setup-error"?7:8;require(t->handle.start(false)==-1,"startup error propagated");require(android::base::GetProperty("sys.usb.ffs.mtp.ready","")=="0","failed start withdraws ready");fault=0;t->close();return;}
    t->start();
    if(c=="zero"||c=="negative"||c=="null"||c=="oversize"){
        std::vector<unsigned char> p(513);mtp_event e{16,p.data()};if(c=="zero")e.length=0;if(c=="negative")e.length=-1;if(c=="null")e.data=nullptr;if(c=="oversize")e.length=513;require(t->handle.sendEvent(e)==-1&&errno==EINVAL,"invalid event rejected");
    }else if(c=="after-close"){t->close();require(t->send(1)==-1&&errno==ESHUTDOWN,"reject after close");}
    else if(c=="double-close"){t->close();t->close();}
    else if(c=="start-twice"){require(t->handle.start(false)==-1&&errno==EBUSY,"second start rejected");require(t->send(12)==0,"first generation retained");require(t->readBytes(16)==packet(12),"first generation functional");}
    else if(c=="ordered"||c=="copy-buffer"||c=="concurrent"){
        int n=c=="copy-buffer"?1:64;
        if(c=="concurrent"){
            std::vector<std::thread> v;for(int i=0;i<4;i++)v.emplace_back([&,i]{for(int j=0;j<16;j++)require(t->send(i*16+j)==0,"concurrent send accepted");});for(auto& x:v)x.join();
        }else for(int i=0;i<n;i++){auto p=packet(i);require(t->handle.sendEvent({16,p.data()})==0,"send accepted");memset(p.data(),0xff,p.size());}
        auto b=t->readBytes(n*16);std::set<unsigned> seen;for(int i=0;i<n;i++){unsigned val;memcpy(&val,b.data()+i*16+4,4);require(b[i*16]==16,"copied event buffer");require(val<static_cast<unsigned>(n),"event identity");seen.insert(val);if(c!="concurrent")require(val==static_cast<unsigned>(i),"FIFO ordering");}require(seen.size()==static_cast<size_t>(n),"unique packets");
    }else if(c=="blocked-close"||c=="blocked-destructor"||c=="bounded-queue"||c=="reconnect"){
        t->fill();int accepted=0,rejected=0;int n=c=="bounded-queue"?180:1;
        for(int i=0;i<n;i++){int r=t->send(i);if(r==0)accepted++;else{require(errno==EAGAIN,"queue backpressure explicit");rejected++;}}
        std::this_thread::sleep_for(30ms);
        if(c=="blocked-destructor"){t.reset();return;}
        t->close();
        if(c=="bounded-queue")require(accepted<=129&&rejected>0,"bounded event queue");
        if(c=="reconnect"){t->attach();t->start();require(t->send(999)==0,"reconnect send");require(t->readBytes(16)==packet(999),"no stale event after reconnect");}
    }else if(c=="backpressure-resume"){
        auto bytes=t->fill();require(t->send(123)==0,"enqueue under backpressure");std::this_thread::sleep_for(80ms);t->readBytes(bytes);require(t->readBytes(16)==packet(123),"event resumes once host drains endpoint");
    }else if(c=="close-race"){
        t->fill();std::atomic<bool> go{false};std::thread producer([&]{while(!go){}for(int i=0;i<256;i++)t->send(i);});go=true;t->close();producer.join();require(t->send(1)==-1,"closed generation stays closed");
    }else if(c=="cancel-pending"||c=="cancel-async"||c=="cancel-completed"){
        fault=c=="cancel-pending"?6:c=="cancel-async"?9:10;require(t->send(1)==0,"pending enqueue");auto until=std::chrono::steady_clock::now()+1s;while(submits==0&&std::chrono::steady_clock::now()<until)std::this_thread::sleep_for(1ms);require(submits>0,"request submitted asynchronously");t->close();require(cancels>0,"pending request canceled");
    }else{
        if(c=="completion-eintr")fault=12;else if(c=="completion-eagain")fault=13;else if(c=="event-timeout")fault=11;else if(c=="submit-eintr")fault=1;else if(c=="submit-eagain")fault=2;else if(c=="submit-error")fault=3;else if(c=="short-completion")fault=4;else if(c=="error-completion")fault=5;else if(c=="disconnect")t->intr.reset();else require(false,"known case");
        require(t->send(1)==0,"enqueue before async failure");
        if(fault==1||fault==2||fault==12||fault==13){require(t->readBytes(16)==packet(1),"retry delivers exactly one event");require(submits>=4,"injected transient retries");}
        else{auto until=std::chrono::steady_clock::now()+3s;bool rejected=false;while(std::chrono::steady_clock::now()<until){std::this_thread::sleep_for(10ms);if(t->send(2)==-1&&errno!=EAGAIN){rejected=true;break;}}require(rejected,"permanent transport failure rejects subsequent events");if(c=="event-timeout")require(errno==ETIMEDOUT&&cancels>0,"deadline cancels pending event");}
    }
    t->close();
}
int main(int argc,char** argv){signal(SIGPIPE,SIG_IGN);require(argc==3,"arguments");if(std::string(argv[1])=="native")run<android::MtpFfsHandle>(argv[2]);else run<android::MtpFfsCompatHandle>(argv[2]);std::cout<<"PASS "<<argv[1]<<"/"<<argv[2]<<std::endl;}
