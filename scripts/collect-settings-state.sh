#!/system/bin/sh
# Read-only snapshot of settings storage; never mount or alter settings.
set -u
out=${1:-}
case "$out" in
    /tmp/dijun-settings-*) suffix=${out#/tmp/dijun-settings-} ;;
    *) echo 'Expected /tmp/dijun-settings-N-before or -after' >&2; exit 1 ;;
esac
case "$suffix" in
    ''|*[!0-9a-z-]*) echo 'Invalid output suffix' >&2; exit 1 ;;
esac
command -v timeout >/dev/null 2>&1 || exit 1
mkdir "$out" || exit 1
printf 'file\texit\n' > "$out/commands.tsv"
status=0
capture() {
    file=$1
    shift
    timeout -s KILL 5 "$@" > "$out/$file" 2>&1
    rc=$?
    printf '%s\t%s\n' "$file" "$rc" >> "$out/commands.tsv"
    [ "$rc" = 0 ] || status=1
}
capture recovery.log cat /tmp/recovery.log
capture uptime.txt cat /proc/uptime
capture mounts.txt cat /proc/mounts
capture mountinfo.txt cat /proc/self/mountinfo
capture properties.txt getprop
capture processes.txt ps -AT
capture dmesg.txt dmesg
capture logcat.txt logcat -b all -d
capture recovery-binary-sha256.txt sha256sum /system/bin/recovery /system/lib64/libgui2.so
capture input-devices.txt cat /proc/bus/input/devices
capture getevent-devices.txt getevent -pl
capture touch-raw-mode.txt cat /sys/class/touch/touch_dev/enable_touch_raw
capture fstab.txt cat /etc/recovery.fstab
pid=$(pidof recovery)
case "$pid" in
    ''|*[!0-9]*) printf 'No unique recovery PID: %s\n' "$pid" > "$out/recovery-process-skipped.txt" ;;
    *) capture recovery-maps.txt cat "/proc/$pid/maps" ;;
esac
capture storage-metadata.txt ls -ldZ /mnt /mnt/vendor /mnt/vendor/persist \
    /mnt/vendor/persist/TWRP /mnt/vendor/persist/TWRP/.twrp_settings
# Avoid traversing an unmounted persist directory or creating a write probe.
if awk '$2 == "/mnt/vendor/persist" { found=1 } END { exit !found }' /proc/mounts; then
    capture capacity.txt df -k /mnt/vendor/persist
    capture settings-stat.txt stat /mnt/vendor/persist/TWRP/.twrp_settings
    capture settings-sha256.txt sha256sum /mnt/vendor/persist/TWRP/.twrp_settings
else
    echo 'PERSIST_NOT_MOUNTED; no mount attempted.' > "$out/storage-skipped.txt"
fi
printf '%s\n' "$status" > "$out/collection-exit.txt"
echo "Snapshot: $out (status=$status; missing files can be diagnostic)"
exit "$status"
