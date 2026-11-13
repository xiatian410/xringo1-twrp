#pragma once
#include <algorithm>
#include <cerrno>
#include <condition_variable>
#include <cstring>
#include <deque>
#include <functional>
#include <mutex>
#include <vector>
#include <unistd.h>
#include "IMtpHandle.h"
namespace android {
using Bytes=std::vector<uint8_t>;
inline uint32_t word(const Bytes& b,size_t n){uint32_t x=0;for(int i=0;i<4;++i)x|=uint32_t(b.at(n+i))<<(i*8);return x;}
inline void put(Bytes& b,uint64_t n,size_t count){for(size_t i=0;i<count;++i)b.push_back(n>>(i*8));}
inline Bytes packet(uint16_t type,uint16_t code,uint32_t tx,const Bytes& payload={}){
 Bytes b;put(b,12+payload.size(),4);put(b,type,2);put(b,code,2);put(b,tx,4);b.insert(b.end(),payload.begin(),payload.end());return b;
}
struct Peer {
 std::mutex mutex;std::condition_variable cv;std::deque<Bytes> input;
 std::vector<Bytes> output,events;bool disconnected=false;bool receive_fail=false;bool receive_cancel=false;bool receive_short_success=false;int starts=0,closes=0;
 std::vector<uint64_t> transaction_lifetimes;
 uint64_t active_transaction=0;
 bool transaction_lifetime_error=false;
 bool reset_pending=false,reset_next_write=false,reset_receive=false,reset_send=false;
 bool reset_disconnect=false;
 int read_errno=0;
};
inline Peer peer;
inline std::function<void(int)> receiving_probe;
class FixtureHandle:public IMtpHandle {
 public:
 explicit FixtureHandle(int){}
 bool consumeReset() {std::lock_guard l(peer.mutex);bool r=peer.reset_pending;peer.reset_pending=false;return r;}
 void beginTransaction(uint32_t id) override {
  std::lock_guard l(peer.mutex);
  if(peer.active_transaction)peer.transaction_lifetime_error=true;
  peer.active_transaction=(uint64_t{1}<<32)|id;
  peer.transaction_lifetimes.push_back(peer.active_transaction);
 }
 void endTransaction() override {
  std::lock_guard l(peer.mutex);
  if(!peer.active_transaction)peer.transaction_lifetime_error=true;
  peer.active_transaction=0;
  peer.transaction_lifetimes.push_back(0);
 }
 int start(bool) override {std::lock_guard l(peer.mutex);++peer.starts;return 0;}
 void close() override {std::lock_guard l(peer.mutex);++peer.closes;peer.cv.notify_all();}
 int read(void* out,size_t len) override {
  std::unique_lock l(peer.mutex);peer.cv.wait(l,[]{return peer.disconnected||!peer.input.empty();});
  if(peer.input.empty()){errno=EIO;return -1;}
  if(peer.input.front().empty()){peer.input.pop_front();peer.reset_pending=true;errno=peer.reset_disconnect?ESHUTDOWN:ECANCELED;return -1;}
  auto& b=peer.input.front();auto n=std::min(len,b.size());memcpy(out,b.data(),n);
  b.erase(b.begin(),b.begin()+n);if(b.empty())peer.input.pop_front();
  if(peer.read_errno){errno=peer.read_errno;peer.read_errno=0;}
  return n;
 }
 int write(const void* data,size_t n) override {std::lock_guard l(peer.mutex);if(peer.reset_next_write){peer.reset_next_write=false;peer.reset_pending=true;errno=ECANCELED;return -1;}const auto* p=static_cast<const uint8_t*>(data);peer.output.emplace_back(p,p+n);peer.cv.notify_all();return n;}
 int sendEvent(mtp_event e) override {std::lock_guard l(peer.mutex);const auto* p=static_cast<const uint8_t*>(e.data);peer.events.emplace_back(p,p+e.length);peer.cv.notify_all();return 0;}
 int receiveFile(mtp_file_range r,bool) override {
  if(receiving_probe)receiving_probe(r.fd);
  {std::lock_guard l(peer.mutex);if(peer.receive_cancel||peer.reset_receive){
   if(peer.reset_receive){peer.reset_receive=false;peer.reset_pending=true;}
   // Model transport cancellation discarding the remaining data phase while
   // retaining the next command. The server must not parse payload as commands.
   size_t left=r.length;
   while(left&&!peer.input.empty()){auto&b=peer.input.front();size_t n=std::min(left,b.size());b.erase(b.begin(),b.begin()+n);left-=n;if(b.empty())peer.input.pop_front();}
   errno=ECANCELED;return -1;
  }if(peer.receive_fail){errno=ENOSPC;return -1;}if(peer.receive_short_success)return 0;}
  char b[4096];size_t left=r.length;off_t off=r.offset;
  while(left){int n=read(b,std::min(left,sizeof(b)));if(n<=0)return -1;if(pwrite(r.fd,b,n,off)!=n)return -1;left-=n;off+=n;}return 0;
 }
 int sendFile(mtp_file_range r) override {
  {std::lock_guard l(peer.mutex);if(peer.reset_send){peer.reset_send=false;peer.reset_pending=true;errno=ECANCELED;return -1;}}
  if(r.length>1024*1024){errno=EFBIG;return -1;}
  Bytes data(r.length);auto n=pread(r.fd,data.data(),data.size(),r.offset);if(n<0)return -1;data.resize(n);
  auto p=packet(2,r.command,r.transaction_id,data);write(p.data(),p.size());return 0;
 }
};
}
