#!/system/bin/sh
# Opt-in diagnostic for the inspected OS4 Xiaomi/Synaptics log callbacks.
# Changes log verbosity temporarily, never raw/report mode, IRQ or reset.
set -u
out=/tmp/dijun-touch-v1-debug
node=/sys/class/touch/touch_dev/touch_log_level
mkdir -p "$out" || exit 1
command -v timeout >/dev/null 2>&1 || exit 1
cat "$node" > "$out/log-level-before.txt" || exit 1
old=$(awk '/^current xiaomi_touch log_level = / {gsub(",", "", $5); print $5, $9}' "$out/log-level-before.txt")
case "$old" in [0-5]' '[0-5]) ;; *) echo 'Cannot parse original log levels; stopped without changing them.'; exit 1 ;; esac
restore() {
    printf '%s\n' "$old" > "$node" || return 1
    cat "$node" > "$out/log-level-after.txt" || return 1
    restored=$(awk '/^current xiaomi_touch log_level = / {gsub(",", "", $5); print $5, $9}' "$out/log-level-after.txt")
    [ "$restored" = "$old" ]
}
trap restore EXIT
trap 'exit 130' INT TERM HUP
cat /proc/uptime > "$out/start-uptime.txt"
dmesg > "$out/dmesg-before.txt"
cat /sys/bus/platform/devices/synaptics_tcm*/synaptics_tcm/info > "$out/controller-info.txt" 2>&1
cat /sys/class/touch/touch_dev/enable_touch_raw > "$out/raw-mode.txt" 2>&1
# value0 controls wrapper logs; value1>3 enables Synaptics debug_log_flag.
echo '3 4' > "$node" || exit 1
cat "$node" > "$out/log-level-during.txt"
observed=$(awk '/^current xiaomi_touch log_level = / {gsub(",", "", $5); print $5, $9}' "$out/log-level-during.txt")
[ "$observed" = '3 4' ] || { echo 'Debug level readback failed; stopping and restoring original levels.'; exit 1; }
# Stream kernel logs immediately so a busy driver cannot overwrite the ring.
timeout -s KILL 10 dmesg -w > "$out/dmesg-stream.txt" 2>&1 &
logger=$!
echo 'SWIPE NOW for 8 seconds; do not press power.'
cat /proc/interrupts > "$out/interrupts-before.txt"
timeout -s KILL 8 getevent -lt > "$out/events.txt" 2>&1
event_exit=$?
echo "$event_exit" > "$out/getevent-exit.txt"
cat /proc/interrupts > "$out/interrupts-after.txt"
wait "$logger"
logger_exit=$?
echo "$logger_exit" > "$out/dmesg-stream-exit.txt"
dmesg > "$out/dmesg-after.txt"
cat /proc/uptime > "$out/end-uptime.txt"
if ! restore; then
    echo 'ERROR: could not verify original log verbosity restoration.' >&2
    exit 1
fi
trap - EXIT
case "$event_exit:$logger_exit" in
    124:124|124:137|137:124|137:137) ;;
    *) echo 'ERROR: capture ended unexpectedly; keep partial logs. Original verbosity restored.' >&2; exit 1 ;;
esac
echo "DONE: $out (original log verbosity restored)"
