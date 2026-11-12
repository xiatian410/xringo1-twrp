// A deliberately harmless host updater. All writes use private fixture paths.
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <signal.h>
#include <unistd.h>
int main(int argc,char** argv) {
  assert(argc==4 && std::string(argv[1])=="3" && std::string(argv[3])=="./package.fixture");
  FILE* marker=fopen("child-ran","w");assert(marker);fputs("ran\n",marker);fclose(marker);
  FILE* input=fopen(argv[3],"r");assert(input);char name[128];assert(fgets(name,sizeof(name),input));fclose(input);
  std::string scenario=name;
  FILE* out=fdopen(atoi(argv[2]),"w");assert(out);
  if(scenario=="normal")fputs("ui_print installed fixture\nprogress 0.5 2\nset_progress 0.75\nwipe_cache\n",out);
  else if(scenario=="signed-progress")fputs("progress 0.5 2\n",out);
  else if(scenario=="missing-fraction")fputs("progress\n",out);
  else if(scenario=="missing-seconds")fputs("progress 0.5\n",out);
  else if(scenario=="missing-set")fputs("set_progress\n",out);
  else if(scenario=="nan")fputs("set_progress nan\n",out);
  else if(scenario=="infinite")fputs("progress inf 2\n",out);
  else if(scenario=="negative")fputs("set_progress -0.5\n",out);
  else if(scenario=="too-large")fputs("progress 1.1 2\n",out);
  else if(scenario=="bad-number")fputs("set_progress 0.3garbage\n",out);
  else if(scenario=="bad-seconds")fputs("progress 0.5 2x\n",out);
  else if(scenario=="negative-seconds")fputs("progress 0.5 -1\n",out);
  else if(scenario=="huge-seconds")fputs("progress 0.5 9999999999999999999999999\n",out);
  else if(scenario=="log-empty")fputs("log\nui_print\n",out);
  else if(scenario=="exit-error") {fputs("ui_print expected updater failure\n",out);fclose(out);return 7;}
  else if(scenario=="signal") {fclose(out);raise(SIGTERM);return 9;}
  fclose(out);return 0;
}
