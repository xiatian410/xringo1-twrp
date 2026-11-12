// Host list publication -> backend -> real LVGL builders. Filesystem presence is supplied.
#include <cassert>
#include <cstdio>
#include <format>
#include <map>
#include <mutex>
#include <set>
#include <string>
#include <vector>
#include "lvgl.h"
#include "backend/mount_backend.h"
#include "core/ui_helpers.h"
#include "pages/mount_page.h"
#include "pages/select_storage_page.h"
#include "core/ui_event_guard.h"

#define LOGINFO(...) ((void)0)
#define LOGERR(...) std::fprintf(stderr,__VA_ARGS__)
namespace twrp_operation_executor {
struct executor { std::recursive_mutex lock; std::recursive_mutex& mutex(){return lock;} };
executor& instance(){static executor e;return e;}
struct guard {std::lock_guard<std::recursive_mutex> lock;guard(std::recursive_mutex&m):lock(m){}};
}
struct UnitConversion {static std::string FormatBytes(unsigned long long n){return std::to_string(n)+" fixture bytes";}};
struct DataManager {static std::string GetCurrentStoragePath(){return "/data/media";}};
struct TWPartition {
  std::string mount_point_,display_name_,storage_name_,storage_path_;
  bool can_be_mounted_=true,is_present_=true,is_storage_=false,mounted=false;
  unsigned long long free_=4096;
  bool IsMounted()const{return mounted;}
};
#include "partition-list.inc"
class TWPartitionManager {
 public:
  std::vector<TWPartition*> partitions_;
  mutable std::mutex list_snapshot_mutex_;
  mutable std::map<std::string,std::vector<PartitionList>> list_snapshots_;
  mutable std::map<std::string,uint64_t> list_revisions_;
  mutable std::set<std::string> list_subscriptions_;
  void GetPartitionList(const std::string&,std::vector<PartitionList>*)const;
  bool TryGetPartitionList(const std::string&,std::vector<PartitionList>*)const;
  void RefreshPartitionListSnapshots()const;
} PartitionManager;
#include "partition-methods.inc"
namespace gui2_backend {
struct twrp_mount_backend {
  std::vector<mount_target> targets();
  std::vector<storage_device> storages();
};
#include "backend-methods.inc"
}
namespace gui2_i18n {extern const language_pack kEnglish;}
static void flush(lv_display_t*d,const lv_area_t*,uint8_t*){lv_display_flush_ready(d);}
static unsigned count_text(lv_obj_t*o,const std::string&text){
  unsigned found=lv_obj_check_type(o,&lv_label_class)&&lv_label_get_text(o)==text;
  for(uint32_t i=0;i<lv_obj_get_child_count(o);++i)found+=count_text(lv_obj_get_child(o,i),text);
  return found;
}
int main(int argc,char**argv){
  assert(argc==2); const std::string scenario=argv[1];
  std::vector<TWPartition> parts;
  // Filesystem alternatives are already grouped in the shipped fstab inventory.
  // Classification/presence below are explicit fixtures, not a ProcessFstabLine execution.
#include "fixture.inc"
  if(scenario=="shipped-otg-paths")for(auto&p:parts){
    if(p.mount_point_=="/usbotg-1-2")p.mount_point_=p.storage_path_="/storage/usbotg-sdz-2";
    if(p.mount_point_=="/usbotg-1-10")p.mount_point_=p.storage_path_="/storage/usbotg-sdz-10";
  }
  for(auto&p:parts)PartitionManager.partitions_.push_back(&p);
  const auto locate=[&](const std::string&path)->TWPartition&{
    for(auto&p:parts)if(p.mount_point_==path)return p;
    assert(false);return parts.front();
  };
  if(scenario=="absent-nv")locate("/mnt/vendor/nvdata").is_present_=false;
  if(scenario=="duplicate-input-names")for(auto&p:parts)if(p.can_be_mounted_&&!gui2_backend::is_otg_path(p.mount_point_))p.display_name_="Internal Storage";
  if(scenario=="data-absent")locate("/data").is_present_=false;
  gui2_backend::twrp_mount_backend backend;
  assert(backend.targets().empty()&&backend.storages().empty()); // subscriptions before first publication
  PartitionManager.RefreshPartitionListSnapshots();
  auto targets=backend.targets();auto storages=backend.storages();
  if(scenario=="shipped-otg-paths"){
    assert(targets[targets.size()-2].name=="OTG sdz 2"&&targets.back().name=="OTG sdz 10");
    assert(storages[1].name.starts_with("OTG sdz 2")&&storages[2].name.starts_with("OTG sdz 10"));
  }
  std::vector<std::string> paths;
  for(const auto&t:targets)paths.push_back(t.mount_point);
  std::set<std::string> unique(paths.begin(),paths.end());assert(unique.size()==paths.size());
  assert(!unique.contains("/nvram")&&!unique.contains("/proinfo")&&!unique.contains("/misc"));
  for(const auto*path:{"/mnt/vendor/nvcfg","/mnt/vendor/nvdata","/mnt/vendor/protect_f","/mnt/vendor/protect_s"})
    assert(!unique.contains(path));
  // Internal list/classification still retains these original declarations.
  assert(locate("/mnt/vendor/nvcfg").can_be_mounted_);
  assert(storages.size()==(scenario=="data-absent"?2u:3u));
  for(const auto&s:storages)assert(s.path=="/data/media"||gui2_backend::is_otg_path(s.path));
  for(int i=0;i<30;++i){PartitionManager.RefreshPartitionListSnapshots();assert(backend.targets().size()==targets.size());assert(backend.storages().size()==storages.size());}
  if(scenario=="remove-readd"){
    auto&disk=locate("/usbotg-1-2");disk.is_present_=false;
    PartitionManager.RefreshPartitionListSnapshots();assert(backend.storages().size()==storages.size()-1);
    disk.is_present_=true;PartitionManager.RefreshPartitionListSnapshots();
    assert(backend.storages().size()==storages.size());
  }
  lv_init();auto*display=lv_display_create(1440,3200);std::vector<uint32_t> pixels(1440*64);
  lv_display_set_color_format(display,LV_COLOR_FORMAT_XRGB8888);
  lv_display_set_buffers(display,pixels.data(),nullptr,pixels.size()*4,LV_DISPLAY_RENDER_MODE_PARTIAL);
  lv_display_set_flush_cb(display,flush);
  auto&ui=gui2_core::ui;static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(true);
  ui.width=1440;ui.height=3200;ui.scale=1.2f;ui.content_width=1344;ui.content_left=48;
  ui.outer_margin=48;ui.card_height=192;ui.card_gap=24;ui.nav_height=156;ui.cards_top_gap=24;
  ui.text_font=ui.status_font=ui.brand_font=&lv_font_montserrat_16;
  auto*root=lv_screen_active();gui2_core::disable_scrolling(root);
  std::vector<int> indices;for(size_t i=0;i<targets.size();++i)indices.push_back(i);
  gui2_pages::mount_page_options options;
  options.content=root;options.metrics=&ui;options.strings=&gui2_i18n::kEnglish;
  options.targets=targets.data();options.target_count=targets.size();options.target_indices=indices.data();
  options.storage_name="Internal Storage";options.storage_free="4096 fixture bytes";
  auto view=gui2_pages::build_mount_page(options);lv_obj_update_layout(root);
  assert(view.rows.size()==targets.size());
  for(size_t i=0;i<targets.size();++i){
    auto*toggle=view.rows[i].toggle;assert(toggle);
    auto*card=lv_obj_get_parent(toggle);
    assert(count_text(card,targets[i].name)==1);
    std::printf("MOUNT %s\t%s\n",targets[i].mount_point.c_str(),targets[i].name.c_str());
  }
  unsigned internal_count=count_text(root,"Internal Storage");
  const size_t expected_internal=scenario=="duplicate-input-names"?1+targets.size()-2:1;
  assert(internal_count==expected_internal);
  lv_obj_clean(root);indices.clear();for(size_t i=0;i<storages.size();++i)indices.push_back(i);
  gui2_pages::select_storage_page_options select;
  select.content=root;select.metrics=&ui;select.strings=&gui2_i18n::kEnglish;
  select.storages=storages.data();select.storage_count=storages.size();select.storage_indices=indices.data();
  gui2_pages::build_select_storage_page(select);lv_obj_update_layout(root);
  auto*body=lv_obj_get_child(root,0);assert(lv_obj_get_child_count(body)==storages.size());
  for(size_t i=0;i<storages.size();++i){
    assert(count_text(lv_obj_get_child(body,i),storages[i].name)==1);
    std::printf("STORAGE %s\t%s\n",storages[i].path.c_str(),storages[i].name.c_str());
  }
  std::printf("PASS scenario=%s mount_rows=%zu storage_rows=%zu internal_labels=%u\n",scenario.c_str(),targets.size(),storages.size(),internal_count);
  lv_deinit();
}
