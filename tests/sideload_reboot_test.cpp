// Appended to the shared private-process lifecycle fixture preamble.
static int syncs=0,log_updates=0,actual_reboots=0;static std::string reboot_argument_seen;
enum RebootCommand {CURRENT,SYSTEM,RECOVERY,POWER_OFF,BOOTLOADER,DOWNLOAD,EDL,FSATBOOTD};
namespace TWFunc {void UpdateLogFile(){++log_updates;}int TwReboot(RebootCommand c){++actual_reboots;reboot_argument_seen=std::to_string(c);return 0;}}
static void fixture_sync(){++syncs;}
// REBOOT_HEADER
namespace gui2_backend {
const reboot_capabilities& twrp_reboot_backend::capabilities() const {capabilities_={true,true,true,true,true,true,true,false};if(scenario=="unsupported-target")capabilities_.fastboot=false;return capabilities_;}
std::string twrp_reboot_backend::active_slot()const{return {};}
bool twrp_reboot_backend::set_active_slot(boot_slot){return false;}
bool twrp_reboot_backend::usb_fastboot()const{return false;}
void twrp_reboot_backend::set_usb_fastboot(bool){}
bool twrp_reboot_backend::os_installed()const{return true;}
#define sync fixture_sync
// REBOOT_METHODS
#undef sync
}
static bool reboot_requested=false,startup_failed=false;static void* startup=nullptr;
struct BackgroundFixture {bool busy=false;bool command_running(){return busy;}};
static BackgroundFixture* background=nullptr;
static gui2_backend::reboot_backend* reboot=nullptr;
static gui2_backend::sideload_backend* sideload=nullptr;
// GUI_METHODS
// FINAL_REBOOT
static void pipe_handler(int){}
static int child_fixture(int fd){
 uint32_t command=3;if(scenario=="system"||scenario=="ors-system")command=2;
 if(scenario.find("fastboot")!=std::string::npos||scenario=="unsupported-target")command=4;
 if(scenario=="recovery"||scenario=="ors-recovery")command=5;
 if(scenario=="rescue")command=6;
 char message[8]={'C','O','M','D',0,0,0,0};memcpy(message+4,&command,4);::write(fd,message,8);
 if(scenario=="ack-fail"){::shutdown(fd,SHUT_RDWR);return 0;}
 char reply[8];android::base::ReadFully(fd,reply,8);return 0;
}
static int script_sideload(){int ret_val=0,install_cmd=0,sideload=0;
// ORS_BRANCH
 return ret_val;
}
static int property_set(const char*,const char*){return 0;}
static bool wait_until(const std::function<bool()>& fn){auto end=std::chrono::steady_clock::now()+std::chrono::seconds(4);while(!fn()){if(std::chrono::steady_clock::now()>end)return false;std::this_thread::yield();}return true;}
int main(int argc,char**argv){
 if(argc==3&&std::string(argv[1])=="--socket_fd"){scenario=getenv("REBOOT_FIXTURE");return child_fixture(atoi(argv[2]));}
 scenario=argv[1];setenv("REBOOT_FIXTURE",scenario.c_str(),1);::signal(SIGPIPE,pipe_handler);
 gui2_backend::twrp_reboot_backend rebooter;reboot=&rebooter;
 bool rejected=scenario=="rescue"||scenario=="ack-fail"||scenario=="restore-fail";
 if(scenario=="cancel-pending"||scenario=="cancelled-before-return"){
  std::atomic<bool> token=false;Device::BuiltinAction action=Device::NO_ACTION;
  CHECK(twrp_sideload("/",&action,&token)==INSTALL_REBOOT);token=true;RequestMiniAdbdExit(&token);
 }else if(scenario.starts_with("ors-"))CHECK(script_sideload()==1);
 else {
  gui2_backend::twrp_sideload_backend backend;sideload=&backend;CHECK(backend.start(false,false));
  CHECK(wait_until([&]{return backend.status().state!=gui2_backend::sideload_state::RUNNING;}));
  CHECK(backend.status().state==(rejected?gui2_backend::sideload_state::FAILED:gui2_backend::sideload_state::DONE));
  backend.acknowledge();sideload=nullptr;
 }
 CHECK(GetMiniAdbdPid()==0);CHECK(waits==1);CHECK(mtp);CHECK(!actual_reboots);

 if(scenario=="wrong-token") {std::atomic<bool> unrelated=true;RequestMiniAdbdExit(&unrelated);}
 if(scenario=="pending-blocks-session") {Device::BuiltinAction a=Device::REBOOT;CHECK(twrp_sideload("/",&a)==INSTALL_ERROR);CHECK(forks==1);}
 if(scenario=="startup-gate"){startup=reinterpret_cast<void*>(1);poll_external_reboot();CHECK(!reboot_requested);startup=nullptr;}
 if(scenario=="background-gate"){BackgroundFixture b;b.busy=true;background=&b;poll_external_reboot();CHECK(!reboot_requested);background=nullptr;}
 if(scenario=="worker-gate"){
  struct Running:gui2_backend::sideload_backend{bool start(bool,bool)override{return false;}void cancel()override{}gui2_backend::sideload_status status()override{return {gui2_backend::sideload_state::RUNNING};}void acknowledge()override{}} b;
  sideload=&b;poll_external_reboot();CHECK(!reboot_requested);sideload=nullptr;
 }
 if(scenario=="storage-gate"){
  std::mutex gate;std::condition_variable cv;bool held=false,release=false;
  std::thread owner([&]{
   std::unique_lock storage(twrp_operation_executor::instance().mutex());
   std::unique_lock lock(gate);held=true;cv.notify_all();cv.wait(lock,[&]{return release;});
  });
  {std::unique_lock lock(gate);cv.wait(lock,[&]{return held;});}
  auto started=std::chrono::steady_clock::now();poll_external_reboot();
  CHECK(std::chrono::steady_clock::now()-started<std::chrono::milliseconds(250));
  CHECK(!reboot_requested&&syncs==0&&DataManager::GetStrValue("tw_reboot_arg").empty());
  {std::lock_guard lock(gate);release=true;}cv.notify_all();owner.join();
  // The next ordinary GUI poll must consume the original pending action.
 }
 poll_external_reboot();
 bool expected=!rejected&&scenario!="unsupported-target"&&scenario!="write-fail"&&scenario!="cancel-pending"&&scenario!="cancelled-before-return";
 CHECK(reboot_requested==expected);CHECK(gui2_loop_should_exit(nullptr)==expected);CHECK(!actual_reboots);
 if(expected){CHECK(syncs==1);std::string target="bootloader";RebootCommand command=BOOTLOADER;
  if(scenario=="system"||scenario=="ors-system"){target="system";command=SYSTEM;}
  if(scenario.find("fastboot")!=std::string::npos){target="fastboot";command=FSATBOOTD;}
  if(scenario=="recovery"||scenario=="ors-recovery"){target="recovery";command=RECOVERY;}
  CHECK(DataManager::GetStrValue("tw_reboot_arg")==target);Reboot();CHECK(actual_reboots==1);CHECK(reboot_argument_seen==std::to_string(command));
 }
 Device::BuiltinAction a=Device::NO_ACTION;CHECK(!TakeMiniAdbdRebootAction(&a));
 CHECK(unsafe_kills==0);int status;CHECK(waitpid(-1,&status,WNOHANG)==-1&&errno==ECHILD);
 std::cout<<"failures="<<failures<<" reboots="<<actual_reboots<<" syncs="<<syncs<<" waits="<<waits<<"\n";return failures?1:0;
}
