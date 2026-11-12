#include <cerrno>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <sys/stat.h>
#include <unistd.h>
#include "backend/twrp_operation.h"
namespace gui2_backend {void operation_start(const std::string&){}void operation_end(int){}}
static std::string fault;
extern "C" {
size_t __real_fwrite(const void*,size_t,size_t,FILE*);
int __real_mkstemp(char*);int __real_rename(const char*,const char*);int __real_fsync(int);
size_t __wrap_fwrite(const void*p,size_t s,size_t n,FILE*f){
 if(fault=="no-space"){errno=ENOSPC;return 0;}
 if(fault=="short-write")return __real_fwrite(p,s,n/2,f);
 return __real_fwrite(p,s,n,f);
}
int __wrap_mkstemp(char*p){if(fault=="read-only"){errno=EROFS;return -1;}return __real_mkstemp(p);}
int __wrap_rename(const char*a,const char*b){if(fault=="rename-error"){errno=EIO;return -1;}return __real_rename(a,b);}
int __wrap_fsync(int fd){struct stat st;assert(fstat(fd,&st)==0);if(fault=="directory-sync-error"&&S_ISDIR(st.st_mode)){errno=EIO;return -1;}return __real_fsync(fd);}
}
static std::string disk(){std::ifstream f(std::string(TW_PERSIST_DIR)+"/"+TW_SETTINGS_FILE,std::ios::binary);assert(f);return {std::istreambuf_iterator<char>(f),{}};}
int main(int argc,char**argv){
 assert(argc==3);std::string kind=argv[1],scenario=argv[2];
 // Keep the real /mnt/... path shape: a /tmp prefix would trigger the
 // partition manager's intentional ramdisk shortcut and mask old lookup bugs.
 assert(chroot(FIXTURE_ROOT)==0&&chdir("/")==0);
 TWPartition part;part.mount_point_=std::filesystem::path(TW_PERSIST_DIR).parent_path().string();
 PartitionManager.partitions_={&part};
 DataManager::consts_.SetConst();
 DataManager::kBackingFile=std::string(TW_PERSIST_DIR)+"/"+TW_SETTINGS_FILE;
 assert(store.set_persistent("tw_gui2_swap_navigation","0"));
 // Prepare an existing valid file independently of the path lookup under test.
 InfoManager seed("/seed");seed.SetFileVersion(FILE_VERSION);seed["tw_gui2_swap_navigation"]="0";
 assert(seed.SaveValues()==0);assert(rename("/seed",DataManager::kBackingFile.c_str())==0);
 const auto original=disk();
 if(scenario=="mount-on-save"||scenario=="mount-denied")part.mounted=false;
 if(scenario=="mount-denied")part.can_mount=false;
 if(scenario=="uninitialized-backing")DataManager::kBackingFile.clear();
 if(scenario=="constant-key")DataManager::consts_["tw_gui2_swap_navigation"]="0";
 if(scenario=="long-field")DataManager::persist_["unrelated_field"]=std::string(511,'x');
 fault=scenario;
 lv_init();auto*display=lv_display_create(480,640);std::vector<uint32_t>pixels(480*640);
 lv_display_set_color_format(display,LV_COLOR_FORMAT_XRGB8888);lv_display_set_buffers(display,pixels.data(),nullptr,pixels.size()*4,LV_DISPLAY_RENDER_MODE_FULL);lv_display_set_flush_cb(display,flush);
 pointer=lv_indev_create();lv_indev_set_type(pointer,LV_INDEV_TYPE_POINTER);lv_indev_set_display(pointer,display);lv_indev_set_read_cb(pointer,read_pointer);
 gui2_core::configure_click_guard(pointer,hardware);static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(true);
 ui.width=480;ui.height=640;ui.scale=.4f;ui.outer_margin=16;ui.content_width=448;ui.text_font=&lv_font_montserrat_16;
 auto*screen=lv_screen_active();gui2_core::disable_scrolling(screen);int index=0;
 auto create=kind=="check"?gui2_components::create_check_row:gui2_components::create_switch_row;
 auto*toggle=create(screen,ui,"Swap navigation",false,general_setting_event_cb,&index);
 auto*card=lv_obj_get_parent(toggle);lv_obj_set_pos(card,16,60);lv_obj_update_layout(screen);
 const auto target=center(lv_obj_get_child(card,0));point(target,true);point(target,false);
 const bool success=scenario=="existing-mount"||scenario=="mount-on-save";
 assert(general_settings_items[0].value==success);
 assert(lv_obj_has_state(toggle,LV_STATE_CHECKED)==success);
 assert(store.get_string("tw_gui2_swap_navigation","missing")== (success?"1":"0"));
 assert(navigation_calls==(success?1:0)&&hw.calls==(success?1:0));
 if(success)assert(disk()!=original);
 else if(scenario=="directory-sync-error"){
   // Rename published the complete new file; failed directory fsync is not rollback.
   InfoManager published(DataManager::kBackingFile);published.SetFileVersion(FILE_VERSION);
   assert(published.LoadValues()==0&&published.GetStrValue("tw_gui2_swap_navigation")=="1");
 }else assert(disk()==original);
 if(scenario=="mount-on-save")assert(part.mounts==1&&part.mounted);
 if(scenario=="mount-denied")assert(part.mounts==1&&!part.mounted);
 if(!success){
  fault.clear();part.can_mount=true;DataManager::consts_.Clear();
  DataManager::kBackingFile=std::string(TW_PERSIST_DIR)+"/"+TW_SETTINGS_FILE;
  if(scenario=="long-field"){DataManager::persist_.Clear();assert(store.set_persistent("tw_gui2_swap_navigation","0"));}
  point(target,true);point(target,false);
  assert(general_settings_items[0].value&&lv_obj_has_state(toggle,LV_STATE_CHECKED));
  assert(navigation_calls==1&&hw.calls==1&&store.get_int("tw_gui2_swap_navigation",0)==1);
 }
 InfoManager loaded(std::string(TW_PERSIST_DIR)+"/"+TW_SETTINGS_FILE);loaded.SetFileVersion(FILE_VERSION);
 assert(loaded.LoadValues()==0&&loaded.GetStrValue("tw_gui2_swap_navigation")=="1");
 int temps=0;for(const auto&e:std::filesystem::directory_iterator(TW_PERSIST_DIR))if(e.path().filename().string().find(".tmp.")!=std::string::npos)++temps;assert(temps==0);
 gui2_core::configure_click_guard(nullptr,nullptr);lv_deinit();
 std::printf("PASS %s/%s disk roundtrip, UI rollback/retry, mounts=%d feedback=%d\n",argv[1],argv[2],part.mounts,hw.calls);
}
