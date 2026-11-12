// Real GUI policy methods; partition discovery, state presentation and destructive I/O are doubles.
#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "mount_backend.h"
#include "wipe_backend.h"
#include "tools_backend.h"
#include "install_backend.h"
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define TW_HAS_DATA_MEDIA "media"
#define TW_EXTERNAL_PATH "external"
namespace twrp_operation_executor {
struct executor {std::recursive_mutex m;auto& mutex(){return m;}};
executor& instance(){static executor e;return e;}
using guard=std::lock_guard<std::recursive_mutex>;
}
struct DataManager {
 static inline std::map<std::string,std::string> values;
 static std::string GetStrValue(const std::string& k){return values[k];}
 static std::string GetCurrentStoragePath(){return "/data/media";}
 static void GetValue(const std::string&k,std::string&v){v=values[k];}
 static void GetValue(const std::string&,int&v){v=1;}
 static void SetValue(const std::string&k,const std::string&v){values[k]=v;}
 static void SetValue(const std::string&k,int v){values[k]=std::to_string(v);}
};
static int mutations=0,starts=0,updates=0;
static void operation_start(const char*){++starts;}
static void operation_end(int){}
namespace gui2_console {template<class... T>void info(T... ){} template<class... T>void log_error(T... ){} }
namespace UnitConversion {std::string FormatBytes(unsigned long v){return std::to_string(v);}}
namespace TWFunc {bool IsPathExists(const std::string&){return true;}}
struct PartitionList {std::string display_name,mount_point;bool slot_select=false;};
struct TWPartition {
  std::string GetMountPoint(){return mount_point_;}
 std::string mount_point_,display_name_="fixture",current_file_system_="ext4";
 unsigned long size_=1,used_=0,free_=1,backup_size_=1;
 bool is_present_=true,removable_=false;
 bool CanRepair(){return true;}bool CanResize(){return true;}
};
struct Manager {
 TWPartition resolved;std::vector<PartitionList> list;
 TWPartition* FindPartitionByPath(const std::string&p){resolved.mount_point_=p=="/alias"?"/mnt/vendor/nvdata":p;return &resolved;}
 void TryGetPartitionList(const std::string&,std::vector<PartitionList>*o){*o=list;}
 bool WipeByPath(const std::string&,const std::string& = ""){++mutations;return true;}
 bool RepairByPath(const std::string&,bool){++mutations;return true;}
 bool ResizeByPath(const std::string&,bool){++mutations;return true;}
 bool FlashImage(const std::string&,const std::string&){++mutations;return true;}
 bool FactoryReset(){++mutations;return true;}bool WipeBatteryStats(){++mutations;return true;}
 bool WipeRotateData(){++mutations;return true;}bool WipeDalvikCache(){++mutations;return true;}
 bool FormatData(){++mutations;return true;}bool WipeMediaFromData(){++mutations;return true;}
 bool WipeAndroidSecure(){++mutations;return true;}void UpdateSystemDetails(){++updates;}
} PartitionManager;
namespace gui2_backend {
struct twrp_wipe_backend {
 std::atomic<bool>running_{false};
 std::vector<wipe_target> targets();bool start_wipe(const std::vector<std::string>&);
 bool start(std::vector<std::string> a); // explicit synchronous dispatch boundary
};
struct twrp_tools_backend {
 std::atomic<bool>running_{false};std::thread worker_;std::mutex mutex_;tool_state state_=tool_state::IDLE;
 ~twrp_tools_backend(){if(worker_.joinable())worker_.join();}
 void join_finished_thread(){if(worker_.joinable())worker_.join();}
 bool details(const std::string&,partition_details*);bool start(tool_job,const std::string&,const std::string&);
 void run(tool_job,const std::string&,const std::string&);
};
struct twrp_install_backend {
 std::atomic<bool>running_{false};std::thread worker_;std::mutex mutex_;install_state state_=install_state::IDLE;
 install_status status_;std::chrono::steady_clock::time_point started_;
 ~twrp_install_backend(){if(worker_.joinable())worker_.join();}
 void join_finished_thread(){if(worker_.joinable())worker_.join();}
 std::vector<image_target>image_targets();bool start_image(const std::string&,const std::string&,bool);
 void run_image(std::string,std::string,bool);
};
#include "methods.inc"
bool twrp_wipe_backend::start(std::vector<std::string>a){return wipe(a.at(0),[](auto,int,bool){})==0;}
void twrp_tools_backend::run(tool_job j,const std::string&p,const std::string&v){
 int r=j==tool_job::REPAIR?repair(p):j==tool_job::RESIZE?resize(p):changefilesystem(p,v);
 state_=r==0?tool_state::DONE:tool_state::FAILED;running_=false;
}
}
int main(int argc,char**argv){
 assert(argc==3);std::string p=argv[1];bool blocked=std::string(argv[2])=="1";
 using namespace gui2_backend;twrp_wipe_backend w;
 auto clean=[](){mutations=starts=updates=0;DataManager::values.clear();};
 if(p=="injection"||p=="empty"){
  clean();assert(!w.start_wipe(p=="empty"?std::vector<std::string>{}:std::vector<std::string>{"/data;/nvdata"}));
  assert(mutations==0&&DataManager::values.empty());twrp_install_backend i;
  assert(!i.start_image("/tmp/test.img",p=="empty"?"":"/boot;/nvdata",false));return 0;
 }
 if(p=="stale"){
  clean();DataManager::SetValue("tw_wipe_list","/data;/alias;");
  assert(wipe("LIST",[](auto,int,bool){})==1&&mutations==0&&starts==0);return 0;
 }
 PartitionManager.list={{"candidate",p},{"normal","/data"}};
 assert(w.targets().size()==(blocked&&p!="/alias"?1u:2u));
 {twrp_install_backend i;assert(i.image_targets().size()==(blocked&&p!="/alias"?1u:2u));}
 clean();assert(w.start_wipe({"/data",p})==!blocked);assert(mutations==(blocked?0:2));
 if(blocked)assert(DataManager::values.empty()&&starts==0);
 clean();DataManager::SetValue("tw_wipe_list","/data;"+p+";");
 assert(wipe("LIST",[](auto,int,bool){})==(blocked?1:0));assert(mutations==(blocked?0:2));
 for(auto j:{tool_job::REPAIR,tool_job::RESIZE,tool_job::CHANGE_FILE_SYSTEM}){
  clean();twrp_tools_backend t;partition_details d;assert(t.details(p,&d)==!blocked);
  assert(t.start(j,p,"ext4")==!blocked);if(t.worker_.joinable())t.worker_.join();assert(mutations==(blocked?0:1));
  clean();int r=j==tool_job::REPAIR?repair(p):j==tool_job::RESIZE?resize(p):changefilesystem(p,"ext4");
  assert(r==(blocked?1:0)&&mutations==(blocked?0:1));
 }
 clean();{twrp_install_backend i;assert(i.start_image("/tmp/test.img",p,false)==!blocked);
 if(i.worker_.joinable())i.worker_.join();assert(mutations==(blocked?0:1));if(blocked)assert(DataManager::values.empty());}
 clean();{twrp_install_backend i;i.run_image("/tmp/test.img",p,false);assert(mutations==(blocked?0:1));if(blocked)assert(i.state_==install_state::FAILED);}
 printf("PASS %s blocked=%d\n",p.c_str(),blocked);
}
