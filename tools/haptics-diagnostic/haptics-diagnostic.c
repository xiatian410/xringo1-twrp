/* Independent evdev diagnostic. Never calibrates or writes persist/sysfs.
 * No arguments prints usage; --inspect only queries. --play explicitly submits
 * the current dijun Recovery SINE request. --stock-long uses the reviewed OS4
 * HAL CUSTOM {0,31}, gain 100, and explicit timed erase. The two cross controls
 * isolate waveform from gain. Not a Recovery fix.
 * Use an external bounded observer:
 * an ioctl may wait inside a kernel driver and has no userspace timeout here.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/input.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

_Static_assert(sizeof(struct ff_effect) == 48, "requires 64-bit evdev ABI");
_Static_assert(sizeof(struct input_event) == 24, "requires 64-bit evdev ABI");

static long long milliseconds(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return -1;
    return (long long)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static void begin(const char *operation) {
    printf("BEGIN %s monotonic_ms=%lld\n", operation, milliseconds());
    fflush(stdout);
}

static void result(const char *operation, long value, int saved_errno, long long start) {
    long long end = milliseconds();
    printf("END %s result=%ld errno=%d elapsed_ms=%lld monotonic_ms=%lld\n",
           operation, value, value < 0 ? saved_errno : 0,
           start >= 0 && end >= 0 ? end - start : -1, end);
    fflush(stdout);
}

static bool bit(const unsigned long *bits, unsigned int number) {
    const unsigned int size = 8 * sizeof(*bits);
    return (bits[number / size] & (1UL << (number % size))) != 0;
}

int main(int argc, char **argv) {
    const bool stock_long = argc == 4 && strcmp(argv[1], "--stock-long") == 0;
    const bool sine_gain = argc == 4 && strcmp(argv[1], "--sine-gain100") == 0;
    const bool custom_existing = argc == 4 && strcmp(argv[1], "--custom-existing-gain") == 0;
    const bool custom_wave = stock_long || custom_existing;
    const bool set_gain = stock_long || sine_gain;
    const bool play = custom_wave || sine_gain || (argc == 4 && strcmp(argv[1], "--play") == 0);
    const bool inspect = argc == 3 && strcmp(argv[1], "--inspect") == 0;
    int duration = 0;
    if (!play && !inspect) {
        fprintf(stderr, "Usage: %s --inspect /dev/input/eventN\n"
                        "       %s --play /dev/input/eventN DURATION_MS (1..10000)\n"
                        "       %s --stock-long /dev/input/eventN DURATION_MS (1..1000, reviewed OS4 only)\n"
                        "       %s --sine-gain100 /dev/input/eventN DURATION_MS (1..1000)\n"
                        "       %s --custom-existing-gain /dev/input/eventN DURATION_MS (1..1000, reviewed OS4 only)\n"
                        "--play uses SINE period=8 magnitude=64.\n"
                        "--stock-long writes gain=100 and CUSTOM {0,31}; erase stops playback.\n"
                        "Success means syscall acceptance only.\n",
                argv[0], argv[0], argv[0], argv[0], argv[0]);
        return 2;
    }
    const char *path = argv[2];
    const char *suffix = path + (strlen(path) >= 16 ? 16 : strlen(path));
    if (strncmp(path, "/dev/input/event", 16) != 0) {
        /* strlen("/dev/input/event") is 16. */
        fprintf(stderr, "Expected an explicit /dev/input/eventN path\n");
        return 2;
    }
    if (*suffix == '\0' || strspn(suffix, "0123456789") != strlen(suffix)) return 2;
    if (play) {
        char *end;
        errno = 0;
        long parsed = strtol(argv[3], &end, 10);
        if (errno || end == argv[3] || *end || parsed < 1 || parsed > ((custom_wave || sine_gain) ? 1000 : 10000)) return 2;
        duration = (int)parsed;
    }
    printf("ABI ff_effect=%zu input_event=%zu mode=%s path=%s\n",
           sizeof(struct ff_effect), sizeof(struct input_event), stock_long ? "stock-long" : sine_gain ? "sine-gain100" : custom_existing ? "custom-existing-gain" : (play ? "play" : "inspect"), path);
    begin("open");
    long long start = milliseconds();
    int fd = open(path, (play ? O_RDWR : O_RDONLY) | O_CLOEXEC);
    result("open", fd, errno, start);
    if (fd < 0) return 1;
    int exit_code = 1;
    char name[128] = {0};
    unsigned long capabilities[(FF_CNT + 8 * sizeof(unsigned long) - 1) /
                               (8 * sizeof(unsigned long))] = {0};
    begin("name");
    start = milliseconds();
    int status = ioctl(fd, EVIOCGNAME(sizeof(name)), name);
    result("name", status, errno, start);
    if (status < 0) goto done;
    name[sizeof(name) - 1] = '\0';
    printf("DEVICE name=%s\n", name);
    begin("capabilities");
    start = milliseconds();
    status = ioctl(fd, EVIOCGBIT(EV_FF, sizeof(capabilities)), capabilities);
    result("capabilities", status, errno, start);
    if (status < 0) goto done;
    printf("CAPABILITIES periodic=%d sine=%d custom=%d gain=%d\n",
           bit(capabilities, FF_PERIODIC), bit(capabilities, FF_SINE),
           bit(capabilities, FF_CUSTOM), bit(capabilities, FF_GAIN));
    if (!inspect && (strcmp(name, "cs40l26_input") != 0 ||
                     !bit(capabilities, FF_PERIODIC) ||
                     (!custom_wave && !bit(capabilities, FF_SINE)) ||
                     (custom_wave && !bit(capabilities, FF_CUSTOM)) ||
                     (set_gain && !bit(capabilities, FF_GAIN)))) {
        fprintf(stderr, "Playback requires cs40l26_input with PERIODIC and the selected waveform/gain capabilities\n");
        goto done;
    }
    if (inspect) { exit_code = 0; goto done; }
    struct ff_effect effect = {0};
    short custom[2] = {0, 31};
    effect.type = FF_PERIODIC;
    effect.id = -1;
    effect.replay.length = duration;
    effect.u.periodic.waveform = FF_SINE;
    effect.u.periodic.period = 8;
    effect.u.periodic.magnitude = 64;
    if (custom_wave) {
        // Exact reviewed stock HAL long-on request; lifetime is controlled by
        // userspace erase, not replay.length. No arbitrary wave/gain interface.
        memset(&effect.u, 0, sizeof(effect.u));
        effect.replay.length = 0;
        effect.u.periodic.waveform = FF_CUSTOM;
        effect.u.periodic.custom_len = 2;
        effect.u.periodic.custom_data = custom;
        printf("REQUEST stock_long_id=31 custom_words=0,31 gain=%s erase_after_ms=%d replay_ms=0\n",
               set_gain ? "100" : "unchanged", duration);
    } else {
        printf("REQUEST replay_ms=%d period_ms=8 magnitude=64 gain=%s\n", duration,
               set_gain ? "100" : "unchanged");
    }
    if (set_gain) {
        struct input_event gain = {0};
        gain.type = EV_FF;
        gain.code = FF_GAIN;
        gain.value = 100;
        begin("gain");
        start = milliseconds();
        ssize_t gain_written = write(fd, &gain, sizeof(gain));
        result("gain", gain_written, errno, start);
        if (gain_written != sizeof(gain)) goto done;
    }
    printf("EFFECT_HEX ");
    for (size_t i = 0; i < sizeof(effect); ++i) printf("%02x", ((unsigned char *)&effect)[i]);
    putchar('\n');
    begin("upload");
    start = milliseconds();
    status = ioctl(fd, EVIOCSFF, &effect);
    result("upload", status, errno, start);
    if (status < 0) goto done;
    printf("EFFECT_ID %d\n", effect.id);
    if (effect.id < 0) {
        fprintf(stderr, "Upload returned no allocated effect ID\n");
        goto done;
    }
    struct input_event event = {0};
    event.type = EV_FF;
    event.code = effect.id;
    event.value = 1;
    begin("play");
    start = milliseconds();
    ssize_t written = write(fd, &event, sizeof(event));
    result("play", written, errno, start);
    if (written != sizeof(event)) goto done;
    /* Keep the owning fd alive through replay (or stock long-on). Closing it earlier may erase
     * the effect. This delay is separate from the driver's completion wait. */
    struct timespec remaining = {duration / 1000, (duration % 1000) * 1000000L};
    while (nanosleep(&remaining, &remaining) < 0) {
        if (errno != EINTR) goto done;
    }
    begin("erase");
    start = milliseconds();
    status = ioctl(fd, EVIOCRMFF, (int)effect.id);
    result("erase", status, errno, start);
    if (status < 0) goto done;
    puts("ACCEPTED upload/play/erase; physical output unverified");
    exit_code = 0;
done:
    begin("close");
    start = milliseconds();
    status = close(fd);
    result("close", status, errno, start);
    return status < 0 ? 1 : exit_code;
}
