// Host executable payload: creates one private result and sends updater protocol.
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#ifndef UPDATER_TAG
#define UPDATER_TAG "generic"
#endif
int main(int argc,char** argv) {
  assert(argc==4 && strcmp(argv[1],"3")==0 && strcmp(argv[3],"/packages/test.zip")==0);
  FILE* f=fopen("/case-name","r");assert(f);char name[128]{};assert(fgets(name,sizeof(name),f));fclose(f);
  FILE* out=fdopen(atoi(argv[2]),"w");assert(out);
  if(strcmp(name,"updater-nonzero")==0) {fclose(out);return 7;}
  if(strcmp(name,"updater-badprogress")==0) {fputs("progress\n",out);fclose(out);return 0;}
  f=fopen("/packages/result.txt","w");assert(f);fprintf(f,"%s\n",UPDATER_TAG);fclose(f);
  fputs("ui_print private ZIP fixture\nprogress 0.5 1\nset_progress 1\nwipe_cache\n",out);
  fclose(out);return 0;
}
