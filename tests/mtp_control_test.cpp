#include <algorithm>
#include <cstdarg>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <string>
#include <unistd.h>
#include <sys/ioctl.h>
#include "MtpDescriptors.h"
#include "MtpFfsHandle.h"
#include "mtp.h"

// FunctionFS boundary: a SETUP owns exactly one data transfer. Wrong-direction
// ep0 access stalls it; successful/short I/O consumes it. Ordinary descriptors
// and all unrelated operations still use host system calls.
static int control = -1, bulk_in = -1, bulk_out = -1;
static usb_ctrlrequest setup{};
static bool pending = false, stalled = false;
static std::vector<unsigned char> output, payload{1, 0x40, 0x78, 0x56, 0x34, 0x12};
static std::vector<usb_functionfs_event> events;
static int transfer_error = 0, interruptions = 0, stall_error = EL2HLT;
static int short_by = 0, data_calls = 0, stall_calls = 0;
static int event_error = 0, event_interruptions = 0, event_short = 0;
static int desc_error = 0, desc_interruptions = 0, desc_bad = 0;
static void require(bool ok, const char* msg) {
    if (!ok) { std::cerr << "FAIL " << msg << std::endl; std::_Exit(1); }
}
extern "C" ssize_t __real_read(int, void*, size_t);
extern "C" ssize_t __real_write(int, const void*, size_t);
extern "C" int __real_ioctl(int, unsigned long, ...);
static ssize_t transfer(bool input, void* data, size_t size) {
    require(pending, "one transfer per SETUP (no retry of a consumed short packet)");
    if (input != bool(setup.bRequestType & USB_DIR_IN)) {
        require(size == 0, "stall without consuming payload");
        ++stall_calls; stalled = true; pending = false; errno = stall_error; return -1;
    }
    ++data_calls;
    if (interruptions > 0) { --interruptions; errno = EINTR; return -1; }
    if (transfer_error) { pending = false; errno = transfer_error; return -1; }
    pending = false;
    require(size <= le16toh(setup.wLength), "control reply fits host allocation");
    size_t count = size > size_t(short_by) ? size - short_by : 0;
    if (input) output.assign(static_cast<unsigned char*>(data), static_cast<unsigned char*>(data)+count);
    else { require(count <= payload.size(), "bounded OUT read"); memcpy(data, payload.data(), count); }
    return count;
}
extern "C" ssize_t __wrap_read(int fd, void* data, size_t size) {
    if (fd != control) return __real_read(fd, data, size);
    if (pending) return transfer(false, data, size);
    if (event_interruptions > 0) { --event_interruptions; errno = EINTR; return -1; }
    if (event_error) { errno = event_error; return -1; }
    size_t count = events.size()*sizeof(usb_functionfs_event);
    require(count <= size, "event buffer");
    if (count) memcpy(data, events.data(), count);
    for (auto& event : events) if (event.type == FUNCTIONFS_SETUP) { setup = event.u.setup; pending = true; }
    events.clear();
    return count > size_t(event_short) ? count-event_short : 0;
}
extern "C" ssize_t __wrap_write(int fd, const void* data, size_t size) {
    if (fd != control) return __real_write(fd, data, size);
    return transfer(true, const_cast<void*>(data), size);
}
extern "C" int __wrap_ioctl(int fd, unsigned long request, ...) {
    if (fd == bulk_in || fd == bulk_out) {
        if (request == FUNCTIONFS_ENDPOINT_REVMAP) return 255; // upstream 6.6 initializes num to -1
        require(request == FUNCTIONFS_ENDPOINT_DESC, "actual endpoint descriptor query");
        va_list args; va_start(args, request); auto* d = va_arg(args, usb_endpoint_descriptor*); va_end(args);
        if (desc_interruptions > 0) { --desc_interruptions; errno=EINTR; return -1; }
        if (desc_error && fd == bulk_out) { errno=desc_error; return -1; }
        *d={}; d->bLength=USB_DT_ENDPOINT_SIZE; d->bDescriptorType=USB_DT_ENDPOINT;
        d->bmAttributes=USB_ENDPOINT_XFER_BULK; d->bEndpointAddress=fd==bulk_in?0x85:0x06;
        if (fd==bulk_out) {
            if(desc_bad==1)d->bEndpointAddress=0;
            if(desc_bad==2)d->bEndpointAddress=0x86;
            if(desc_bad==3)d->bEndpointAddress=0x76;
            if(desc_bad==4)d->bmAttributes=USB_ENDPOINT_XFER_INT;
            if(desc_bad==5)d->bDescriptorType=USB_DT_INTERFACE;
        }
        return 0;
    }
    va_list args; va_start(args,request); auto p=va_arg(args,void*); va_end(args); return __real_ioctl(fd,request,p);
}
class Probe : public android::MtpFfsHandle {
public:
    Probe(): MtpFfsHandle(open("/dev/null", O_RDWR)) {
        control=mControl.get(); mBulkIn.reset(open("/dev/null",O_RDWR)); mBulkOut.reset(open("/dev/null",O_RDWR));
        bulk_in=mBulkIn.get(); bulk_out=mBulkOut.get(); require(control>=0&&bulk_in>=0&&bulk_out>=0,"fixture descriptors");
    }
    int request() { return handleControlRequest(&setup); }
    int batch() { return handleEvent(); }
    void canceled(bool value) { mCanceled=value; }
    bool canceled() const { return mCanceled; }
    bool resetSignal() {
#ifdef MTP_RESET_SIGNAL
        return consumeReset();
#else
        return false;
#endif
    }
};
static void request(unsigned char type, unsigned char code, unsigned short size) {
    setup={};setup.bRequestType=type;setup.bRequest=code;setup.wLength=htole16(size);pending=true;
}
static void event(unsigned char type) {
    usb_functionfs_event e{};e.type=type;if(type==FUNCTIONFS_SETUP)e.u.setup=setup;events.push_back(e);
}
static void expectError(int result, int expected) {
    require(result==-1,"failure returned");require(errno==expected,"specific error preserved");
}
static void begin(android::IMtpHandle& handle, uint32_t id) {
#ifdef MTP_TRANSACTION_TRACKING
    handle.beginTransaction(id);
#endif
}
static void finish(android::IMtpHandle& handle) {
#ifdef MTP_TRANSACTION_TRACKING
    handle.endTransaction();
#endif
}
int main(int argc,char** argv) {
    require(argc==2,"case argument");std::string c=argv[1];Probe p;
    begin(p, 0x12345678);
    request(0xa1,MTP_REQ_GET_DEVICE_STATUS,4);
    if(c.rfind("status-",0)==0 || c.rfind("canceled-",0)==0) {
        bool canceled=c.rfind("canceled-",0)==0;p.canceled(canceled);
        unsigned n=std::stoul(c.substr(c.find('-')+1));setup.wLength=htole16(n);
        require(p.request()==0,"status request accepted");
        std::vector<unsigned char> expected=canceled?std::vector<unsigned char>{8,0,0x1f,0x20,0x85,0,6,0}:std::vector<unsigned char>{4,0,1,0x20};
        expected.resize(std::min<size_t>(n,expected.size()));require(output==expected,"exact little-endian status bytes");
        require(p.canceled()==(canceled&&n<8),"retain cancellation until full reply");require(!pending,"completed status SETUP");
    } else if(c=="header-then-full") {
        p.canceled(true);require(p.request()==0&&p.canceled(),"header retains state");
        request(0xa1,MTP_REQ_GET_DEVICE_STATUS,8);require(p.request()==0&&!p.canceled(),"full reply commits state");
        require(output==std::vector<unsigned char>({8,0,0x1f,0x20,0x85,0,6,0}),"full endpoint list after header");
        request(0xa1,MTP_REQ_GET_DEVICE_STATUS,4);require(p.request()==0,"subsequent status");require(output==std::vector<unsigned char>({4,0,1,0x20}),"next status OK");
    } else if(c.rfind("write-",0)==0) {
        p.canceled(true);setup.wLength=htole16(8);
        if(c=="write-eintr"){interruptions=2;require(p.request()==0&&!p.canceled(),"interrupted write retries");require(data_calls==3,"retry count");}
        else {if(c=="write-short")short_by=1;else if(c=="write-error")transfer_error=EIO;else if(c=="write-again")transfer_error=EAGAIN;else transfer_error=EIDRM;
            int r=p.request();if(transfer_error==EIDRM)require(r==0,"superseded setup is not fatal");else expectError(r,transfer_error?transfer_error:EIO);
            require(p.canceled(),"failed reply retains state");require(data_calls==1,"no retry after short or permanent error");}
    } else if(c.rfind("descriptor-",0)==0) {
        p.canceled(true);setup.wLength=htole16(8);
        if(c=="descriptor-eintr"){desc_interruptions=2;require(p.request()==0,"descriptor retry");require(!p.canceled(),"full reply success");}
        else {if(c=="descriptor-error")desc_error=ENODEV;else if(c=="descriptor-zero")desc_bad=1;else if(c=="descriptor-direction")desc_bad=2;else if(c=="descriptor-reserved")desc_bad=3;else if(c=="descriptor-type")desc_bad=4;else desc_bad=5;
            require(p.request()==0&&stalled,"unavailable status stalls SETUP");require(output.empty()&&p.canceled(),"no fabricated endpoint or lost cancel");}
    } else if(c.rfind("reject-",0)==0) {
        if(c=="reject-status-out")setup.bRequestType=0x21;
        if(c=="reject-recipient")setup.bRequestType=0xa2;
        if(c=="reject-vendor")setup.bRequestType=0xc1;
        if(c=="reject-interface")setup.wIndex=htole16(1);
        if(c=="reject-interface-high")setup.wIndex=htole16(256);
        if(c=="reject-value")setup.wValue=htole16(1);
        if(c=="reject-extended")setup.bRequest=MTP_REQ_GET_EXT_EVENT_DATA;
        if(c=="reject-unknown-in")setup.bRequest=0xff;
        if(c=="reject-unknown-out")request(0x21,0xff,6);
        if(c=="reject-cancel-in")request(0xa1,MTP_REQ_CANCEL,6);
        if(c=="reject-cancel-size")request(0x21,MTP_REQ_CANCEL,5);
        if(c=="reject-reset-in")request(0xa1,MTP_REQ_RESET,0);
        if(c=="reject-reset-size")request(0x21,MTP_REQ_RESET,6);
        require(p.request()==0&&stalled,"unsupported setup stalled without killing transport");require(stall_calls==1&&data_calls==0&&!pending,"reject before data phase");
    } else if(c=="stall-failure"||c=="stall-superseded") {
        setup.bRequest=0xff;stall_error=c=="stall-failure"?ENODEV:EIDRM;int r=p.request();
        if(c=="stall-failure")expectError(r,ENODEV);else require(r==0,"superseded stall benign");
    } else if(c.rfind("transaction-",0)==0) {
        finish(p);
        const bool match=c=="transaction-zero"||c=="transaction-max";
        uint32_t requested=0x12345678;
        if(c=="transaction-zero")requested=0;
        if(c=="transaction-max"||c=="transaction-max-mismatch")requested=0xffffffff;
        if(c=="transaction-finished"){begin(p,requested);finish(p);}
        else if(c=="transaction-next-command"){begin(p,requested);finish(p);begin(p,requested+1);}
        else if(c=="transaction-mismatch"||c=="transaction-max-mismatch")begin(p,requested^1);
        else if(match)begin(p,requested);
        else require(c=="transaction-idle","known transaction case");
        for(int i=0;i<4;++i)payload[i+2]=requested>>(8*i);
        request(0x21,MTP_REQ_CANCEL,6);
        int r=p.request();
        if(match)expectError(r,ECANCELED);else require(r==0,"unmatched/idle cancel acknowledged without interruption");
        require(!pending&&data_calls==1&&!stalled,"valid cancel consumes one OUT packet");
    } else if(c=="reset-session-signal"||c=="reset-status-busy"||c=="reset-clears-cancel"||c=="reset-failed-no-signal"||c=="reset-superseded-no-signal"||c=="cancel-no-reset") {
        const bool cancel=c=="cancel-no-reset";
        p.canceled(c=="reset-clears-cancel");
        request(0x21,cancel?MTP_REQ_CANCEL:MTP_REQ_RESET,cancel?6:0);
        if(c=="reset-failed-no-signal")transfer_error=EIO;
        if(c=="reset-superseded-no-signal")transfer_error=EIDRM;
        int r=p.request();
        if(transfer_error==EIDRM)require(r==0,"superseded setup ignored");else expectError(r,transfer_error?transfer_error:ECANCELED);
        if(cancel||transfer_error)require(!p.resetSignal(),"Cancel/failed Reset never requests session reset");
        else {
            if(c=="reset-status-busy"){
                output.clear();request(0xa1,MTP_REQ_GET_DEVICE_STATUS,64);
                require(p.request()==0&&output==std::vector<unsigned char>({4,0,0x19,0x20}),"pending Reset reports DeviceBusy");
            }
            if(c=="reset-clears-cancel")require(!p.canceled(),"Reset clears prior device cancellation");
            require(p.resetSignal()&&!p.resetSignal(),"Reset signal consumed exactly once");
            output.clear();request(0xa1,MTP_REQ_GET_DEVICE_STATUS,4);
            require(p.request()==0&&output==std::vector<unsigned char>({4,0,1,0x20}),"Reset consumption releases busy status");
        }
    } else if(c.rfind("cancel-",0)==0||c.rfind("reset-",0)==0) {
        bool cancel=c.rfind("cancel-",0)==0;request(0x21,cancel?MTP_REQ_CANCEL:MTP_REQ_RESET,cancel?6:0);
        int expected=ECANCELED;
        if(c=="cancel-short"){short_by=1;expected=EPROTO;}
        if(c=="cancel-code"){payload[1]=0x41;expected=EPROTO;}
        if(c=="cancel-error"||c=="reset-error"){transfer_error=EIO;expected=EIO;}
        if(c=="cancel-eintr"||c=="reset-eintr")interruptions=2;
        if(c=="cancel-superseded")transfer_error=EIDRM;
        int r=p.request();if(transfer_error==EIDRM)require(r==0,"superseded cancel benign");else expectError(r,expected);
        require(!pending,"OUT setup consumed");require(data_calls==((c=="cancel-eintr"||c=="reset-eintr")?3:1),"single data transfer plus EINTR only");
    } else if(c.rfind("events-",0)==0) {
        pending=false;int expected=0;
        if(c=="events-eof")expected=ESHUTDOWN;
        else if(c=="events-error"){event_error=EIO;expected=EIO;}
        else if(c=="events-again")event_error=EAGAIN;
        else if(c=="events-superseded")event_error=EIDRM;
        else if(c=="events-short"){event(FUNCTIONFS_ENABLE);event_short=1;expected=EPROTO;}
        else if(c=="events-lifecycle"||c=="events-eintr") {event(FUNCTIONFS_BIND);event(FUNCTIONFS_ENABLE);event(FUNCTIONFS_SUSPEND);event(FUNCTIONFS_RESUME);if(c=="events-eintr")event_interruptions=2;}
        else if(c=="events-disable-enable"||c=="events-unbind-enable"){event(c=="events-disable-enable"?FUNCTIONFS_DISABLE:FUNCTIONFS_UNBIND);event(FUNCTIONFS_ENABLE);expected=ESHUTDOWN;}
        else if(c=="events-unknown-enable"){event(255);event(FUNCTIONFS_ENABLE);expected=EPROTO;}
        else if(c=="events-status-enable"){event(FUNCTIONFS_SETUP);event(FUNCTIONFS_ENABLE);}
        else if(c=="events-cancel-enable"||c=="events-cancel-disable"){request(0x21,MTP_REQ_CANCEL,6);event(FUNCTIONFS_SETUP);event(c=="events-cancel-enable"?FUNCTIONFS_ENABLE:FUNCTIONFS_DISABLE);expected=c=="events-cancel-enable"?ECANCELED:ESHUTDOWN;}
        else if(c=="events-reset-disable"){request(0x21,MTP_REQ_RESET,0);event(FUNCTIONFS_SETUP);event(FUNCTIONFS_DISABLE);expected=ESHUTDOWN;}
        else if(c=="events-disable-status"){event(FUNCTIONFS_DISABLE);event(FUNCTIONFS_SETUP);expected=ESHUTDOWN;}
        else if(c=="events-stall-enable"){setup.bRequest=0xff;event(FUNCTIONFS_SETUP);event(FUNCTIONFS_ENABLE);}
        else require(false,"known event case");
        pending=false;int r=p.batch();if(expected)expectError(r,expected);else require(r==0,"nonterminal event batch succeeds");
        if(c=="events-disable-status"||c=="events-status-enable")require(output==std::vector<unsigned char>({4,0,1,0x20}),"pending setup serviced despite other events");
        if(c=="events-stall-enable")require(stalled,"batch handles unsupported request");
    } else require(false,"known case");
    std::cout<<"PASS "<<c<<std::endl;
}
