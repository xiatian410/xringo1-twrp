#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <deque>
#include "usb_config.hpp"
#include <set>
#include <sys/stat.h>
#include <unistd.h>
#include "action_manager.h"
#include "action_parser.h"
#include "import_parser.h"
#include "parser.h"
#include "util.h"
using namespace android::init;
static ActionManager* am;
static std::map<std::string,std::string> props;
static std::map<std::string,std::string> files,links;
static std::set<std::string> dirs;
static std::string bound,fail;
static int errors=0,misreports=0;
static std::deque<std::pair<std::string,std::string>> controls;
static int run_helper();
static bool hold_controls=false;
static bool upstream_udc=false;
static std::string during_bind;
static void require(bool b,const char* s){if(!b){std::cerr<<"FAIL "<<s<<std::endl;std::exit(1);}}
static const std::string gadget="/config/usb_gadget/g1";
static std::string actual(){if(bound.empty())return "none";auto get=[](const std::string& p){auto i=links.find(p);return i==links.end()?std::string():i->second;};auto a=get(gadget+"/configs/b.1/f1"),b=get(gadget+"/configs/b.1/f2");if(a.ends_with("ffs.mtp"))return b.ends_with("ffs.adb")?"mtp,adb":"mtp";if(a.ends_with("ffs.adb"))return "adb";if(a.ends_with("ffs.fastboot"))return "fastboot";return "broken";}
namespace android::base {
std::string GetProperty(const std::string& k,const std::string& d){auto i=props.find(k);return i==props.end()?d:i->second;}
bool SetProperty(const std::string& k,const std::string& v){props[k]=v;if(am)am->QueuePropertyChange(k,v);if(k=="sys.usb.state"&&v!="error"&&v!="configuring"&&v!=actual()&&!(v=="sideload"&&actual()=="adb")){++misreports;std::cerr<<"MISREPORT "<<v<<" actual="<<actual()<<'\n';}return true;}
bool ReadFileToString(const std::string& p,std::string* out,bool){std::ifstream f(p);if(!f)return false;out->assign(std::istreambuf_iterator<char>(f),{});return true;}
}
namespace android::init {
Result<std::string> ReadFile(const std::string& p){std::ifstream f(p);if(!f)return Error()<<"no file";return std::string(std::istreambuf_iterator<char>(f),{});}
bool is_dir(const char* p){struct stat s{};return stat(p,&s)==0&&S_ISDIR(s.st_mode);}
}
static Result<void> builtin(const BuiltinArguments& in){
 auto& a=in.args;auto cmd=a[0];std::cerr<<"CMD "<<android::base::Join(a,' ')<<'\n';
 if(cmd=="exec"&&a.back()=="/system/bin/dijun-usb-config") {if(run_helper())return Error()<<"helper failed";return {};}
 auto error=[&](const char* s)->Result<void>{++errors;return Error()<<s;};
 if(cmd=="setprop"){android::base::SetProperty(a[1],a[2]);return {};}
 if(cmd=="start"||cmd=="stop"||cmd=="restart"){android::base::SetProperty("init.svc."+a[1],cmd=="stop"?"stopped":"running");return {};}
 if(cmd=="mkdir"){dirs.insert(a[1]);return {};}
 if(cmd=="write"){
  if(a[1]==gadget+"/UDC"){
   // Android common accepts "none" in addition to the upstream newline.
   // Zero-length writes are no-ops; unbinding an unbound gadget is ENODEV.
   if(a[2].empty())return {};
   if(a[2]=="\n"||(!upstream_udc&&a[2]=="none")){if(fail=="unbind"||bound.empty())return error("unbind failure");bound.clear();return {};}
   if(a[2]!="e1ac0000.dwc3")return error("unknown controller");
   if(fail=="bind"||!bound.empty())return error("UDC bind failure");
   bool found=false;for(auto& [k,v]:links)if(k.starts_with(gadget+"/configs/b.1/f")){
    found=true;auto prop=v.ends_with("ffs.mtp")?"sys.usb.ffs.mtp.ready":"sys.usb.ffs.ready";if(props[prop]!="1")return error("descriptors not ready");
   }
   if(!found)return error("no function linked");bound=a[2];
   if(!during_bind.empty()&&links[gadget+"/configs/b.1/f1"].ends_with("ffs.mtp")){auto change=std::exchange(during_bind,"");android::base::SetProperty(change=="request"?"sys.usb.config":"sys.usb.ffs.mtp.ready",change=="request"?"adb":"0");}
   return {};
  }
  if(fail=="attribute"&&a[1].starts_with(gadget))return error("attribute write failed");
  files[a[1]]=a[2];return {};
 }
 if(cmd=="symlink"){
  if(a[2].starts_with(gadget+"/configs/")){if(fail=="link"||!bound.empty()||links.count(a[2]))return error("link busy or exists");if(!dirs.count(a[1]))return error("missing function");}
  links[a[2]]=a[1];return {};
 }
 if(cmd=="rm"){if(fail=="unlink")return error("unlink failed");if(a[1].starts_with(gadget+"/configs/")&&links.count(a[1]))bound.clear();links.erase(a[1]);return {};}
 return {};
}
class FixtureUsb final : public dijun_usb::Platform {
public:
 std::string get(const std::string& k)override{return android::base::GetProperty(k,"");}
 bool set(const std::string& k,const std::string& v)override{
  if(k=="ctl.start"||k=="ctl.stop"){if((fail=="start"&&k=="ctl.start")||(fail=="stop"&&k=="ctl.stop"))return false;controls.emplace_back(k,v);return true;}
  if(fail=="publish"&&k=="sys.usb.state"&&v=="mtp,adb")return false;
  return android::base::SetProperty(k,v);
 }
 std::optional<std::string> read(const std::string& p)override{if(p==gadget+"/UDC"){if(fail=="read")return {};if(fail=="readback"&&!bound.empty())return "wrong-controller";return bound;}auto i=files.find(p);if(i==files.end())return {};return i->second;}
 bool write(const std::string& p,const std::string& v)override{static std::string context;return builtin({{"write",p,v},context}).ok();}
 std::optional<std::vector<std::string>> links()override{std::vector<std::string> v;for(auto& [k,t] : ::links)if(k.starts_with(gadget+"/configs/b.1/"))v.push_back(k.substr(k.find_last_of('/')+1));return v;}
 std::optional<std::string> link(const std::string& p)override{auto i=::links.find(p);if(i==::links.end())return {};return i->second;}
 bool add(const std::string& t,const std::string& p)override{static std::string context;return builtin({{"symlink",t,p},context}).ok();}
 bool remove(const std::string& p)override{static std::string context;return builtin({{"rm",p},context}).ok();}
};
static int run_helper(){FixtureUsb fixture;return dijun_usb::reconcile(fixture);}
class IgnoreSection:public SectionParser{Result<void> ParseSection(std::vector<std::string>&&,const std::string&,int)override{return {};}};
static void drain(){int n=0;while(am->HasMoreCommands()||(!hold_controls&&!controls.empty())){require(++n<10000,"finite action queue");if(am->HasMoreCommands())am->ExecuteOneCommand();if(!hold_controls&&!controls.empty()){auto [k,v]=controls.front();controls.pop_front();android::base::SetProperty("init.svc."+v,k=="ctl.stop"?"stopped":"running");}}}
static void prop(const std::string& k,const std::string& v){android::base::SetProperty(k,v);}
static void config(const std::string& s){prop("sys.usb.config",s);drain();}
static void ready(bool mtp){prop(mtp?"sys.usb.ffs.mtp.ready":"sys.usb.ffs.ready","1");drain();}
int main(int argc,char** argv){
 require(argc==2,"case");require(chroot(".")==0&&chdir("/")==0,"private root");std::string c=argv[1];
 props={{"ro.hardware","O1_asic"},{"ro.debuggable","1"},{"ro.serialno","fixture"},{"ro.product.manufacturer","Xiaomi"},{"ro.product.model","dijun"},{"ro.recovery.usb.vid","18D1"},{"ro.recovery.usb.adb.pid","D001"},{"ro.recovery.usb.fastboot.pid","4EE0"},{"sys.usb.ffs.ready","0"},{"sys.usb.ffs.mtp.ready","0"}};
 upstream_udc=c=="upstream-unbind";
 if(c=="unmanaged-adb")props["sys.usb.controller"]="e1ac0000.dwc3";
 ActionManager manager;am=&manager;
 #define ENTRY(n) {n,{0,100,{false,builtin}}}
 const BuiltinFunctionMap map{ENTRY("ifup"),ENTRY("setprop"),ENTRY("mkdir"),ENTRY("write"),ENTRY("symlink"),ENTRY("rm"),ENTRY("mount"),ENTRY("start"),ENTRY("stop"),ENTRY("restart"),ENTRY("chmod"),ENTRY("chown"),ENTRY("restorecon"),ENTRY("restorecon_recursive"),ENTRY("class_start"),ENTRY("trigger"),ENTRY("hostname"),ENTRY("domainname"),ENTRY("setrlimit"),ENTRY("exec"),ENTRY("export"),ENTRY("copy"),ENTRY("load_system_props"),ENTRY("load_persist_props"),ENTRY("wait"),ENTRY("setenforce"),ENTRY("loglevel"),ENTRY("insmod"),ENTRY("swapon_all"),ENTRY("mount_all"),ENTRY("exec_start"),ENTRY("enable"),ENTRY("setkey"),ENTRY("chroot"),ENTRY("mknod"),ENTRY("rmdir"),ENTRY("interface_start")};
 Action::set_function_map(&map);Parser parser;parser.AddSectionParser("on",std::make_unique<ActionParser>(&manager,nullptr));parser.AddSectionParser("service",std::make_unique<IgnoreSection>());parser.AddSectionParser("import",std::make_unique<ImportParser>(&parser));require(parser.ParseConfig("/init.rc")&&parser.parse_error_count()==0,"parse production rc");
 for(auto event:{"early-init","init","fs"}){manager.QueueEventTrigger(event);drain();}
 ready(false);require(actual()=="adb","initial adb");misreports=errors=0;
 require(files[gadget+"/idVendor"]=="0x18d1"||files[gadget+"/idVendor"]=="0x18D1","initial ADB vendor identity");
 if(c=="rapid-none-mtp"){prop("sys.usb.config","none");prop("sys.usb.config","mtp,adb");drain();ready(false);ready(true);}
 else if(c=="fastboot"||c=="sideload"){config("none");config(c);ready(false);require(actual()==(c=="sideload"?"adb":"fastboot"),"requested single function");}
 else if(c=="none-ack-stop"){
  hold_controls=true;config("none");require(actual()=="none"&&props["sys.usb.state"]!="none","none must wait for service stop");
  hold_controls=false;drain();require(props["sys.usb.state"]=="none"&&props["init.svc.adbd"]=="stopped","none acknowledges stopped owner");
 }
 else if(c=="sideload-busy"){
  config("sideload");require(props["sys.recovery.usb.error"]=="sideload-owner-busy"&&actual()=="none","external owner requires clean handoff");
 }
 else if(c=="sideload-early-ready"||c=="sideload-lost-ready"||c=="sideload-return"){
  config("none");require(props["init.svc.adbd"]=="stopped","normal ADB stopped before minadbd");
  ready(false);config("sideload");require(actual()=="adb"&&props["sys.usb.state"]=="sideload","early minadbd readiness preserved");
  require(props["init.svc.adbd"]=="stopped"&&props["init.svc.minadbd"].empty(),"helper never starts minadbd or regular adbd for sideload");
  if(c=="sideload-lost-ready"){prop("sys.usb.ffs.ready","0");drain();require(actual()=="none"&&props["init.svc.adbd"]=="stopped","lost minadbd readiness detaches only");}
  if(c=="sideload-return"){config("none");config("adb");ready(false);require(actual()=="adb"&&props["sys.usb.state"]=="adb","normal ADB restored after minadbd exit");}
 }
 else if(c=="unmanaged-adb"){config("none");config("adb");ready(false);require(actual()=="adb","generic unmanaged adb retained");}
 else if(c=="invalid-id"||c=="missing-id"){
  props["ro.recovery.usb.fastboot.pid"]=c=="invalid-id"?"10000":"";
  config("fastboot");ready(false);require(actual()=="none"&&props["sys.recovery.usb.error"]=="invalid-usb-id","invalid identity refused");
 }
 else if(c=="configured-id"){
  props["ro.recovery.usb.vid"]="0X18D1";props["ro.recovery.usb.adb.pid"]="0xD001";props["ro.recovery.usb.fastboot.pid"]="0x4EE0";
  config("fastboot");ready(false);require(actual()=="fastboot","prefixed configured identity");
 }
 else if(c=="unknown-config"||c=="unknown-controller"){
  if(c=="unknown-controller")props["sys.usb.controller"]="unexpected";
  config(c=="unknown-config"?"bad":"mtp,adb");require(actual()=="none"&&props["sys.recovery.usb.error"]!="","unsupported request refused");
 }
 else if(c=="stop-error"||c=="delayed-stop"){
  if(c=="stop-error")fail="stop";else hold_controls=true;
  config("fastboot");require(actual()=="none","old gadget detached before owner switch");require(props["init.svc.fastbootd"]!="running","new owner waits for stop");
  if(c=="stop-error")require(props["sys.recovery.usb.error"]!="","stop error visible");
  else{hold_controls=false;drain();ready(false);require(actual()=="fastboot","delayed stop completes");}
 }
 else if(c=="rapid-flips"){
  for(auto mode:{"none","mtp,adb","fastboot","none","adb","mtp,adb"})prop("sys.usb.config",mode);
  drain();ready(false);ready(true);require(actual()=="mtp,adb"&&props["init.svc.fastbootd"]!="running","latest request wins");
 }
 else {
  config("none");config(c=="mtp-only"?"mtp":"mtp,adb");
  if(c=="bind-error")fail="bind";if(c=="link-error")fail="link";
  if(c=="start-error"){config("none");fail="start";config("mtp,adb");}
  if(c=="attribute-error")fail="attribute";
  if(c=="read-error")fail="read";
  if(c=="readback-error")fail="readback";
  if(c=="publish-error")fail="publish";
  if(c=="request-during-bind")during_bind="request";
  if(c=="readiness-during-bind")during_bind="ready";
  if(c=="mtp-first"){ready(true);require(actual()=="none","wait adb ready");ready(false);}else if(c=="both-ready"){prop("sys.usb.ffs.ready","1");prop("sys.usb.ffs.mtp.ready","1");drain();}else{ready(false);ready(true);}
  if(c=="start-error"){require(actual()=="none"&&props["sys.recovery.usb.error"]!="","failed service start not configured");}
  else if(c=="attribute-error"||c=="read-error"||c=="readback-error"||c=="publish-error"){require(actual()=="none"&&props["sys.usb.state"]!="mtp,adb"&&props["sys.recovery.usb.error"]!="","failed operation not published");}
  else if(c=="request-during-bind"||c=="readiness-during-bind"){require(actual()=="adb","mid-transition change reconciled");}
  else if(c=="repeat-ready"){for(int i=0;i<40;i++){prop("sys.usb.ffs.ready","1");prop("sys.usb.ffs.mtp.ready","1");}drain();require(actual()=="mtp,adb","duplicate events idempotent");}
  else if(c=="mtp-ready-restored"){prop("sys.usb.ffs.mtp.ready","0");drain();require(actual()=="adb","ready withdrawal fallback");ready(true);require(actual()=="mtp,adb","ready return restores MTP");}
  else if(c=="adb-ready-lost"){prop("sys.usb.ffs.ready","0");drain();require(actual()=="none","ADB withdrawal detaches combined function");ready(false);require(actual()=="mtp,adb","ADB descriptor return");}
  else if(c=="adb-service-restarting"){prop("init.svc.adbd","restarting");drain();require(actual()=="none"&&props["sys.usb.ffs.ready"]=="0","restart clears stale readiness");prop("init.svc.adbd","running");drain();require(actual()=="none","running alone is not descriptor ready");ready(false);require(actual()=="mtp,adb","fresh descriptors restore combined mode");}
  else if(c=="adb-service-died"){prop("init.svc.adbd","stopped");drain();require(actual()=="none"&&props["sys.usb.ffs.ready"]=="0","service loss clears stale ready");ready(false);require(actual()=="mtp,adb","new ADB service descriptors");}
  else if(c=="owner-swap"){config("fastboot");require(actual()=="none"&&props["sys.usb.ffs.ready"]=="0","ready not reused by fastboot");ready(false);require(actual()=="fastboot"&&props["init.svc.adbd"]=="stopped","new owner isolated");config("adb");ready(false);require(actual()=="adb"&&props["init.svc.fastbootd"]=="stopped","return to ADB");}
  else if(c=="extra-link"){links[gadget+"/configs/b.1/f3"]=gadget+"/functions/ffs.extra";config("mtp,adb");require(actual()=="mtp,adb"&&!links.count(gadget+"/configs/b.1/f3"),"stale extra function removed");}
  else if(c=="unbind-error"||c=="unlink-error"){fail=c=="unbind-error"?"unbind":"unlink";config("none");require(props["sys.usb.state"]=="error","failed cleanup not reported done");fail.clear();config("none");require(actual()=="none"&&props["sys.usb.state"]=="none","cleanup retry");}
  else if(c=="bind-error"||c=="link-error"){require(actual()=="none","failed bind stays unbound");require(props["sys.usb.state"]=="error","failure cannot report configured");}
  else if(c=="disable-mtp"){config("none");config("adb");ready(false);require(actual()=="adb"&&!links.count(gadget+"/configs/b.1/f2"),"MTP removed and ADB restored");}
  else if(c=="mtp-ready-lost"){prop("sys.usb.ffs.mtp.ready","0");drain();require(actual()=="adb","MTP failure restores ADB");}
  else require(actual()==(c=="mtp-only"?"mtp":"mtp,adb"),"requested MTP binding");
 }
 if(!bound.empty()&&props["sys.usb.state"]!="error"){
  auto lower=[](std::string s){std::transform(s.begin(),s.end(),s.begin(),[](unsigned char c){return std::tolower(c);});return s;};
  auto mode=actual();bool mtp=mode=="mtp"||mode=="mtp,adb";
  require(lower(files[gadget+"/idVendor"])==(mtp?"0x2717":"0x18d1"),"bound vendor identity");
  require(lower(files[gadget+"/idProduct"])==(mode=="mtp"?"0xff40":mode=="mtp,adb"?"0xff48":mode=="fastboot"?"0x4ee0":"0xd001"),"bound product identity");
 }
 require(misreports==0,"no state announced before correct binding");require(errors==0||c.ends_with("-error"),"no stale actions or duplicate links");std::cout<<"PASS "<<c<<'\n';
}
