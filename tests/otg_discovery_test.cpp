// Real discovery methods in a private chroot. No actual block device or USB I/O.
#include <algorithm>
#include <cassert>
#include <charconv>
#include <dirent.h>
#include <filesystem>
#include <format>
#include <fstream>
#include <map>
#include <mutex>
#include <ranges>
#include <span>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include "sysfs_device_match.hpp"
#include "mount_backend.h"
namespace fs = std::filesystem;
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
namespace twrp_operation_executor {
struct executor {std::recursive_mutex m;std::recursive_mutex& mutex(){return m;}};
executor& instance(){static executor e;return e;}
using guard=std::lock_guard<std::recursive_mutex>;
}
namespace TWFunc {
bool IsPathExists(const fs::path&p){return fs::exists(p);}
void WriteToFile(const fs::path&p,const std::string&v){std::ofstream(p)<<v;}
std::string GetPath(const std::string&p){return fs::path(p).parent_path().string()+"/";}
}
// Only the block-node mode is supplied. Files are ordinary files in this chroot.
int fixture_stat(const char*p,struct stat*s){int rc=::stat(p,s);if(!rc)s->st_mode=S_IFBLK|0600;return rc;}
struct UeventBlockData {std::string sysfs_path,block_device,type,action,subsystem;};
struct TWPartition {
 std::string sysfs_entry_,mount_point_="/storage/usbotg",primary_block_device_,alternate_block_device_,actual_block_device_,storage_name_="Storage",display_name_,sub_partition_of_;
 bool is_sub_partition_=false,has_sub_partition_=false,is_present_=false,removable_=true,is_storage_=true,can_be_mounted_=false,wildcard_block_device_=true,can_be_wiped_=false,wipe_available_in_gui_=false;
 bool Unmount(bool){return true;}
 bool ProcessFstabLine(const char*,bool,void*);
 void FindActualBlockDevice();
 bool FindWildcardBlockDevices(const std::string&);
 bool FindPartitionSize(){return true;}
};
struct TWPartitionManager {
 std::vector<TWPartition*> partitions_;
 std::map<std::string,std::string> pending_uevent_nodes_;
 bool uevent_resync_pending_=false,uevent_overrun_=false;int uevent_dirty_batches_=0;
 ~TWPartitionManager(){for(auto*p:partitions_)delete p;}
 void RemoveUeventDevices(const std::string&);
 void HandleUevent(const UeventBlockData&);
 void ResyncUeventDevices();void ProcessPendingUeventDevices();void ResetPendingUeventDevices();
 static void ColdbootScan(std::span<const std::string>,const fs::path&,int);
 void Coldboot()const;
 void AddPartition(TWPartition*p){partitions_.push_back(p);}
 static void OutputPartition(TWPartition*){}
 TWPartition* FindPartitionByBlockDevice(const std::string&s){for(auto*p:partitions_)if(p->primary_block_device_==s&&!p->sysfs_entry_.size())return p;return nullptr;}
 TWPartition* FindPartitionByPath(const std::string&s){for(auto*p:partitions_)if(p->mount_point_==s)return p;return nullptr;}
 bool StorageNameInUse(const std::string&s){return std::ranges::any_of(partitions_,[&](auto*p){return p->storage_name_==s;});}
} PartitionManager;
bool TWPartition::ProcessFstabLine(const char*s,bool,void*){std::string v(s);auto n=v.find(' '),e=v.find(' ',n+1);primary_block_device_=v.substr(0,n);mount_point_=v.substr(n+1,e-n-1);return true;}
// Deliberate boundary: device resolution/mount/filesystem probing is not run.
// Wildcard child enumeration below is the original method, with stat mode supplied.
void TWPartition::FindActualBlockDevice(){
 if(wildcard_block_device_){is_present_=false;can_be_mounted_=false;actual_block_device_.clear();if(!FindWildcardBlockDevices(primary_block_device_)&&fs::exists(primary_block_device_)){is_present_=true;can_be_mounted_=true;actual_block_device_=primary_block_device_;}}
 else {actual_block_device_=primary_block_device_;is_present_=fs::exists(actual_block_device_);}
}
#include "methods.inc"
const std::string usb="/devices/platform/soc/e1a40000.xr_usb/e1a40000.dwc3/xhci-hcd.0.auto/usb1/1-1/1-1:1.0/host0/target0:0:0/0:0:0:0/block/";
const std::string ufs="/devices/platform/soc/e1a00000.ufs/host1/target1:0:0/1:0:0:0/block/";
void touch(const fs::path&p){fs::create_directories(p.parent_path());std::ofstream(p)<<"";}
void disk(const std::string&name,const std::string&base,int count,bool nodes=true){
 auto path=fs::path("/sys"+base+name);touch(path/"uevent");fs::create_directories("/sys/block");fs::create_symlink(path,"/sys/block/"+name);
 if(nodes)touch("/dev/block/"+name);
 for(int i=1;i<=count;++i){auto part=name+std::to_string(i);touch(path/part/"partition");touch(path/part/"uevent");if(nodes)touch("/dev/block/"+part);}
}
size_t children(){return std::ranges::count_if(PartitionManager.partitions_,[](auto*p){return p->is_sub_partition_;});}
void no_internal(){for(auto*p:PartitionManager.partitions_)if(p->is_sub_partition_)assert(!p->primary_block_device_.starts_with("/dev/block/sdc"));}
int main(int argc,char**argv){
 assert(argc==3);const std::string mode=argv[1];auto*p=new TWPartition;p->sysfs_entry_=argv[2];PartitionManager.partitions_.push_back(p);
 if(mode=="names"){
  for(auto s:{"/storage/usbotg","/storage/usbotg-sda-1","/usbotg-1-10","/usb-otg","/usb_otg/part"})assert(gui2_backend::is_otg_path(s));
  for(auto s:{"/data/media","/usbotgfoo","/storage/usbotgfoo","/storage/usbotg_backup","/usb-otgfoo"})assert(!gui2_backend::is_otg_path(s));
 }else if(mode=="literal-boundary"){
  p->sysfs_entry_="/devices/usb1";PartitionManager.HandleUevent({"/devices/usb10/block/sdz","sdz","disk","add"});assert(p->primary_block_device_.empty());
 }else if(mode=="controller-pattern"){
  assert(twrp_uevent::MatchesSysfsDevice(p->sysfs_entry_,"/sys"+usb+"sda/sda1"));
  assert(!twrp_uevent::MatchesSysfsDevice(p->sysfs_entry_,"/devices/platform/soc/e.xr_usb/e.fake/xhci-hcd.0.auto/block/sda"));
  assert(!twrp_uevent::MatchesSysfsDevice(p->sysfs_entry_,"/devices/platform/soc/e.xr_usb/e.dwc3/other.0.auto/block/sda"));
  assert(!twrp_uevent::MatchesSysfsDevice(p->sysfs_entry_,"/devices/platform/soc/e.ufs/block/sda"));
 }else if(mode=="usb-with-ufs-name"){
  disk("sdc",usb,2);PartitionManager.HandleUevent({usb+"sdc","sdc","disk","add"});assert(children()==2);
 }else if(mode=="ufs-with-usb-name"){
  disk("sda",ufs,5);PartitionManager.HandleUevent({ufs+"sda","sda","disk","add"});PartitionManager.ResyncUeventDevices();assert(children()==0&&p->primary_block_device_.empty());
 }else if(mode=="hotplug-ufs"){
  disk("sdc",ufs,85);PartitionManager.HandleUevent({ufs+"sdc","sdc","disk","add"});assert(children()==0&&p->primary_block_device_.empty());
 }else if(mode=="hotplug-usb"){
  disk("sda",usb,2);PartitionManager.HandleUevent({usb+"sda","sda","disk","add"});assert(children()==2);assert(PartitionManager.FindPartitionByPath("/storage/usbotg-sda-2"));
  for(int i=0;i<30;++i)PartitionManager.HandleUevent({usb+"sda/sda2","sda2","partition","add"});assert(children()==2);
  PartitionManager.HandleUevent({usb+"sda/sda2","sda2","partition","remove"});assert(children()==1);
  PartitionManager.HandleUevent({usb+"sda/sda2","sda2","partition","add"});assert(children()==2);
  PartitionManager.HandleUevent({usb+"sda","sda","disk","remove"});assert(children()==0&&!p->is_present_);
 }else if(mode=="coldboot"){
  disk("sdc",ufs,85);disk("sda",usb,2);PartitionManager.Coldboot();
  std::string v;std::ifstream("/sys"+ufs+"sdc/uevent")>>v;assert(v.empty());std::ifstream("/sys"+usb+"sda/uevent")>>v;assert(v=="add");
  v.clear();std::ifstream("/sys"+usb+"sda/sda2/uevent")>>v;assert(v=="add");
 }else if(mode=="resync-ufs"){
  disk("sdc",ufs,85);PartitionManager.ResyncUeventDevices();assert(children()==0&&!p->is_present_&&PartitionManager.pending_uevent_nodes_.empty());
 }else if(mode=="resync-mixed"){
  disk("sdc",ufs,85);disk("sda",usb,2);disk("sdz",usb,1);PartitionManager.ResyncUeventDevices();assert(children()==3);no_internal();
  for(int i=0;i<30;++i)PartitionManager.ResyncUeventDevices();assert(children()==3);no_internal();
  fs::remove("/sys/block/sda");PartitionManager.ResyncUeventDevices();assert(children()==1); // stale /dev nodes intentionally retained
  fs::create_symlink("/sys"+usb+"sda","/sys/block/sda");PartitionManager.ResyncUeventDevices();assert(children()==3);no_internal();
 }else if(mode=="pending-nodes"){
  disk("sdc",ufs,85,false);disk("sda",usb,2,false);PartitionManager.ResyncUeventDevices();assert(children()==0&&PartitionManager.pending_uevent_nodes_.size()==3);
  touch("/dev/block/sda");touch("/dev/block/sda1");touch("/dev/block/sda2");PartitionManager.ProcessPendingUeventDevices();assert(children()==2&&PartitionManager.pending_uevent_nodes_.empty());no_internal();
 }else if(mode=="unpartitioned-usb"){
  disk("sda",usb,0);PartitionManager.ResyncUeventDevices();assert(children()==0&&p->is_present_&&p->can_be_mounted_&&p->actual_block_device_=="/dev/block/sda");
 }else assert(false);
 puts("PASS");
}
