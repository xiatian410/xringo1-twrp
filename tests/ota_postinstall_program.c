// Harmless Android ARM64 executable; mode selected by a private regular file.
extern int open(const char*, int, ...);
extern long read(int, void*, unsigned long);
extern long write(int, const void*, unsigned long);
extern int close(int);
extern int atoi(const char*);
extern int strcmp(const char*, const char*);
extern int raise(int);
extern int pause(void);
int main(int argc, char** argv) {
 if (argc != 3 || strcmp(argv[1], "1") || strcmp(argv[2], "3")) return 90;
 char mode[100] = {0}; int fd = open("/work/mode", 0);
 if (fd < 0 || read(fd, mode, sizeof(mode)-1) < 1) return 91;
 close(fd);
 fd = open("/work/program-entered", 1|64|512, 0600);
 const char marker[] = "ARM64 slot=1 progress_fd=3\n";
 if (fd < 0 || write(fd, marker, sizeof(marker)-1) != sizeof(marker)-1) return 92;
 close(fd);
 const char progress[] = "global_progress 0.25\nglobal_progress nan\nglobal_progress 0.75\n";
 if (write(atoi(argv[2]), progress, sizeof(progress)-1) != sizeof(progress)-1) return 93;
 if (!strcmp(mode,"exit7") || !strcmp(mode,"optional-exit7")) return 7;
 if (!strcmp(mode,"exit3")) return 3;
 if (!strcmp(mode,"exit4")) return 4;
 if (!strcmp(mode,"signal15")) { raise(15); return 94; }
 if (!strcmp(mode,"cancel")) for (;;) pause();
 return 0;
}
