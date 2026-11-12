// Production backend list/action policy; core mount and aliases are explicit doubles.
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <mutex>
#include <string>
#include <vector>
#include <android-base/scopeguard.h>
#include "mount_backend.h"
#define LOGERR(...) std::fprintf(stderr,__VA_ARGS__)
namespace twrp_operation_executor {
struct executor {std::recursive_mutex m;auto& mutex(){return m;}};
executor& instance(){static executor e;return e;}
struct guard {std::lock_guard<std::recursive_mutex> g;guard(std::recursive_mutex&m):g(m){}};
}
struct PartitionList {std::string display_name,mount_point;bool selected=false;};
struct TWPartition {
 std::string mount_point_;bool is_fbe_=false;
 static bool DataIsLocked(){return false;}
};
struct Manager {
 std::vector<PartitionList> list;
 TWPartition resolved;
 unsigned mounts=0,unmounts=0,publishes=0,mtp=0;
 void TryGetPartitionList(const std::string&,std::vector<PartitionList>*out){*out=list;}
 TWPartition* FindPartitionByPath(const std::string&p){resolved.mount_point_=p=="/alias"?"/mnt/vendor/nvdata":p;return &resolved;}
 bool MountByPath(const std::string&,bool){++mounts;return true;}
 int UnmountByPath(const std::string&,bool){++unmounts;return 1;}
 bool PrepareDataForDe(bool){++mounts;return true;}
 void AddMtpStorage(const std::string&){++mtp;}
 void RefreshPartitionListSnapshots(){++publishes;}
} PartitionManager;
namespace gui2_backend {
struct twrp_mount_backend {
 std::vector<mount_target> targets();bool set_mounted(const std::string&,bool);
};
// METHODS
}
int main(int argc,char**argv){
 assert(argc==3);std::string path=argv[1];const bool blocked=std::string(argv[2])=="1";
 gui2_backend::twrp_mount_backend backend;
 PartitionManager.list={{"candidate",path,true},{"System","/system",false},{"Data","/data",true}};
 auto rows=backend.targets();
 if(path!="/alias")assert(rows.size()==(blocked?2u:3u));
 for(bool mount:{true,false}){
   auto before=PartitionManager.mounts+PartitionManager.unmounts;
   auto mtp=PartitionManager.mtp;
   assert(backend.set_mounted(path,mount)==!blocked);
   assert(PartitionManager.mounts+PartitionManager.unmounts==before+(blocked?0:1));
   if(blocked)assert(PartitionManager.mtp==mtp);
 }
 // Policy applies only to the GUI: internal core services can still request NV.
 auto before=PartitionManager.mounts;
 assert(PartitionManager.MountByPath("/mnt/vendor/nvdata",true));
 assert(PartitionManager.mounts==before+1);
 printf("PASS %s blocked=%d mounts=%u unmounts=%u\n",path.c_str(),blocked,PartitionManager.mounts,PartitionManager.unmounts);
}
