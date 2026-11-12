// Harmless host updater: private trace, protocol output and a bounded test gate.
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <unistd.h>
#ifndef QUEUE_MODE
#define QUEUE_MODE "clean"
#endif
int main(int argc,char**argv){
 assert(argc==4 && !strcmp(argv[1],"3"));
 FILE*f=fopen("/packages/executed","a");assert(f);fprintf(f,"%s %s\n",argv[3],QUEUE_MODE);fclose(f);
 if(!strcmp(QUEUE_MODE,"hold")){
  f=fopen("/packages/entered","w");assert(f);fclose(f);
  auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
  while(access("/packages/release",F_OK)!=0){assert(std::chrono::steady_clock::now()<deadline);std::this_thread::sleep_for(std::chrono::milliseconds(2));}
 }
 FILE*out=fdopen(atoi(argv[2]),"w");assert(out);
 if(!strcmp(QUEUE_MODE,"wipe")||!strcmp(QUEUE_MODE,"wipe-fail"))fputs("wipe_cache\n",out);
 if(!strcmp(QUEUE_MODE,"badprogress"))fputs("progress\n",out);
 else fputs("progress 0.5 1\nset_progress 1\n",out);
 fclose(out);
 return !strcmp(QUEUE_MODE,"fail")||!strcmp(QUEUE_MODE,"wipe-fail")?7:0;
}
