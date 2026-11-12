/* Harmless Android ARM64 updater; all output is in a private test chroot. */
typedef unsigned long size_t;
extern int open(const char*, int, ...);
extern long read(int, void*, size_t);
extern long write(int, const void*, size_t);
extern int close(int);
extern int atoi(const char*);
extern int strcmp(const char*, const char*);
extern size_t strlen(const char*);
extern int raise(int);
#ifndef UPDATER_TAG
#define UPDATER_TAG "generic"
#endif
static int initialized;
__attribute__((constructor)) static void init(void) { initialized = 41; }
static int emit(int fd, const char* s) {
  size_t len = strlen(s);
  return write(fd, s, len) == (long)len ? 0 : 1;
}
int main(int argc, char** argv) {
  if (initialized != 41 || argc != 4 || strcmp(argv[1], "3") ||
      strcmp(argv[3], "/packages/test.zip")) return 90;
  int fd = open("/case-name", 0);
  char name[128] = {0};
  if (fd < 0 || read(fd, name, sizeof(name)-1) <= 0) return 91;
  close(fd);
  int protocol = atoi(argv[2]);
  fd = open("/packages/target-entered.txt", 1|64|512, 0600);
  if (fd < 0 || emit(fd, "ARM64 constructor=41 api=3 zip=/packages/test.zip\n") || close(fd)) return 97;
  if (!strcmp(name, "updater-nonzero")) return 7;
  if (!strcmp(name, "target-signal")) { raise(15); return 92; }
  if (!strcmp(name, "updater-badprogress")) return emit(protocol, "progress\n");
  if (!strcmp(name, "target-partial-failure")) {
    fd = open("/packages/partial.txt", 1|64|512, 0600);
    if (fd < 0 || emit(fd, "partial ARM64 side effect\n")) return 93;
    close(fd);
    return emit(protocol, "wipe_cache\n") ? 94 : 7;
  }
#ifdef UNDEFINED_SYMBOL
  extern int dijun_updater_missing_symbol(void);
  if (dijun_updater_missing_symbol()) return 95;
#endif
  fd = open("/packages/result.txt", 1|64|512, 0600);
  if (fd < 0 || emit(fd, UPDATER_TAG "\n") || close(fd)) return 96;
  return emit(protocol, "ui_print ARM64 constructor/main ran\nprogress 0.5 1\nset_progress 1\nwipe_cache\n");
}
