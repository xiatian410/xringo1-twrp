#include <cassert>
#include <cstdarg>
#include <cstring>
#include <thread>
#include <chrono>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include "twrpminui/twrp_input.cpp"
#include "gui2/gui2_input.cpp"

int gr_fb_width(){return 1440;}
int gr_fb_height(){return 3200;}
GRRotation gr_get_rotation(){return GRRotation::NONE;}
int property_get(const char*,char* p,const char* d){strcpy(p,d);return strlen(p);}
int vibrate(int){return 0;}
extern "C" int __real_ioctl(int,unsigned long,...);
extern "C" int __wrap_ioctl(int fd,unsigned long request,...){
    va_list ap;va_start(ap,request);void* p=va_arg(ap,void*);va_end(ap);
    if(_IOC_TYPE(request)!='E')return __real_ioctl(fd,request,p);
    unsigned nr=_IOC_NR(request);size_t size=_IOC_SIZE(request);
    memset(p,0,size);
    if(nr==0x06){strncpy(static_cast<char*>(p),"Xiaomi_Touch_Input_0",size);return 20;}
    if(nr==0x02)return 0;
    auto bit=[&](unsigned b){assert(b/8<size);static_cast<unsigned char*>(p)[b/8]|=1u<<(b%8);};
    if(nr==0x20){bit(EV_ABS);bit(EV_KEY);return 0;}
    if(nr==0x20+EV_KEY){bit(BTN_TOUCH);bit(BTN_TOOL_FINGER);return 0;}
    if(nr==0x20+EV_ABS){for(unsigned b:{ABS_MT_SLOT,ABS_MT_TRACKING_ID,ABS_MT_POSITION_X,ABS_MT_POSITION_Y})bit(b);return 0;}
    if(nr>=0x40 && nr<=0x40+ABS_MAX){
        auto* a=static_cast<input_absinfo*>(p);
        unsigned axis=nr-0x40;
        if(axis==ABS_MT_POSITION_X)a->maximum=143999;
        else if(axis==ABS_MT_POSITION_Y)a->maximum=319999;
        else if(axis==ABS_MT_SLOT)a->maximum=9;
        else {errno=EINVAL;return -1;}
        return 0;
    }
    errno=EINVAL;return -1;
}
static void send_event(int fd,int type,int code,int value){
    input_event e{};e.type=type;e.code=code;e.value=value;
    assert(write(fd,&e,sizeof(e))==sizeof(e));
}
static void drain(lv_indev_t* indev,bool pressed){
    for(int i=0;i<300;++i){
        lv_indev_data_t d{};read_cb(indev,&d);
        if((d.state==LV_INDEV_STATE_PRESSED)==pressed){
            if(pressed){assert(abs(d.point.x-644)<=1);assert(abs(d.point.y-1589)<=1);}
            return;
        }
        std::this_thread::yield();
    }
    assert(false && "event did not reach GUI");
}
int main(int argc,char**argv){
    assert(argc==3);std::string node=std::string(argv[1])+"/event3";
    bool late=std::string(argv[2])=="late";
    int writer=-1;
    auto create=[&]{assert(mkfifo(node.c_str(),0600)==0);writer=open(node.c_str(),O_RDWR|O_NONBLOCK);assert(writer>=0);};
    if(!late)create();
    assert(twrp_input_init()==0);auto* indev=gui2_input_init();
    if(late){
        create();
        // Dispatch the actual inotify creation to the production registration path.
        assert(ev_wait(1000)==0);ev_dispatch();
    }
    // Driver registration/capability ioctl is a fixture; FIFO/inotify/epoll/read,
    // metadata init, Type-B parser, touch queue and GUI read callback are real.
    send_event(writer,EV_ABS,ABS_MT_SLOT,0);
    send_event(writer,EV_ABS,ABS_MT_TRACKING_ID,2);
    send_event(writer,EV_KEY,BTN_TOUCH,1);
    send_event(writer,EV_ABS,ABS_MT_POSITION_X,0xfb90);
    send_event(writer,EV_ABS,ABS_MT_POSITION_Y,0x26cb4);
    send_event(writer,EV_SYN,SYN_REPORT,0);drain(indev,true);
    send_event(writer,EV_ABS,ABS_MT_TRACKING_ID,-1);
    send_event(writer,EV_KEY,BTN_TOUCH,0);
    send_event(writer,EV_SYN,SYN_REPORT,0);drain(indev,false);
    twrp_input_exit();close(writer);
    puts(late?"PASS late registration to GUI":"PASS initial registration to GUI");
}
