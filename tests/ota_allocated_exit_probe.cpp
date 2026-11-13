// Isolate model controller lifetime without replaying payload or postinstall.
#include "update_engine/common/logging.h"
int main(int argc,char** argv){
 assert(argc==2);chromeos_update_engine::SetupLogging(true,false);
 DeltaArchiveManifest manifest;assert(manifest.ParseFromString(read("/work/manifest.pb")));
 model_prepare_allocated(manifest);
 if(std::string(argv[1])=="scoped"){
  // The model controller must die with its owning boot-control adapter, before
  // process-wide logging / property singletons start destruction.
  struct Owner {~Owner(){allocated_control->Cleanup();allocated_control.reset();}} owner;
 }
 puts("PROBE main completed");fflush(stdout);return 0;
}
