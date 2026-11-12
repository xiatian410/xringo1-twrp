#!/system/bin/sh
# OS4 Cirrus state collection. No sysfs writes, calibration, FF or mounts.
# Register-backed show callbacks can resume the DSP: save the baseline first.
set -u
if ! command -v timeout >/dev/null 2>&1; then
    echo 'Missing timeout; no collection started.' >&2
    exit 1
fi
out=${1:-/tmp/dijun-haptics-state-$$}
case "$out" in
    /tmp/dijun-haptics-state-*) suffix=${out#/tmp/dijun-haptics-state-} ;;
    *) echo 'Output must be a new /tmp/dijun-haptics-state-N directory.' >&2; exit 1 ;;
esac
case "$suffix" in
    ''|*[!0-9-]*) echo 'Invalid output suffix.' >&2; exit 1 ;;
esac
# Refuse existing directories, including symlinks, rather than mix old logs.
mkdir "$out" || exit 1
status=0
printf 'item\texit\n' > "$out/commands.tsv"
capture() {
    file=$1
    shift
    timeout -s KILL 3 "$@" > "$out/$file" 2>&1
    rc=$?
    printf '%s\t%s\n' "$file" "$rc" >> "$out/commands.tsv"
    [ "$rc" = 0 ] || status=1
}
read_node() {
    node=$1
    printf '\nNODE=%s\n' "$node"
    if [ ! -r "$node" ]; then
        echo 'READ_EXIT=MISSING_OR_UNREADABLE'
        status=1
        return
    fi
    # Bound bytes as well as elapsed time; never open for writing.
    timeout -s KILL 2 head -c 4096 "$node"
    rc=$?
    printf '\nREAD_EXIT=%s\n' "$rc"
    [ "$rc" = 0 ] || status=1
}

capture dmesg-before.txt dmesg
capture interrupts-before.txt cat /proc/interrupts
capture uptime-before.txt cat /proc/uptime
capture recovery.log cat /tmp/recovery.log
capture mounts.txt cat /proc/mounts
capture input-devices.txt cat /proc/bus/input/devices
capture modules.txt cat /proc/modules
capture getprop.txt getprop
profile=$(timeout -s KILL 2 getprop twrp.profile.selected)
profile_rc=$?
printf 'profile-query\t%s\n' "$profile_rc" >> "$out/commands.tsv"
[ "$profile_rc" = 0 ] || status=1
printf '%s\n' "$profile" > "$out/profile.txt"

{
    echo 'No explicit hardware writes, playback, calibration, gain changes or mounts.'
    echo 'Register-backed state reads can wake the DSP and cause PM/mailbox activity.'
    echo 'The before snapshot precedes these reads; do not treat after-only PM as the original fault.'
    echo 'overprotection_gain is an algorithm parameter, not the general evdev FF gain.'
    echo 'No general FF gain readback is available through the inspected attributes.'
    echo 'No recursive sysfs/debugfs reads. No fw_ctrl, max logger, reset or calibration trigger reads.'
    echo 'Per-node READ_EXIT and commands.tsv must be checked; partial results are not success.'
} > "$out/README.txt"

{
    echo 'Only three original per-device haptics calibration files are considered.'
    if awk '$2 == "/mnt/vendor/persist" { found=1 } END { exit !found }' /proc/mounts; then
        for name in vib_cal_z vib_cal_f0 vib_cal_q; do
            read_node "/mnt/vendor/persist/haptics/$name"
        done
    else
        echo 'PERSIST_NOT_MOUNTED: files not read; no mount attempted.'
        status=1
    fi
} > "$out/persist-calibration.txt" 2>&1

{
    echo 'Fixed path metadata only; a missing stock service alias is not itself a driver failure.'
    for path in /sys/bus/i2c/devices/0-0043 \
        /sys/bus/i2c/devices/0-0043/driver \
        /sys/bus/i2c/drivers/xring-smartpa/0-0043 \
        /sys/bus/i2c/drivers/xring-haptic/0-0043; do
        echo "PATH=$path"
        timeout -s KILL 2 ls -ld "$path"
        echo "METADATA_EXIT=$?"
    done
} > "$out/driver-paths.txt" 2>&1

found=0
{
    for input in /sys/class/input/input*; do
        [ -r "$input/name" ] || continue
        name=$(timeout -s KILL 2 head -c 128 "$input/name")
        name_rc=$?
        if [ "$name_rc" != 0 ]; then
            printf 'NAME_READ_ERROR=%s EXIT=%s\n' "$input" "$name_rc"
            status=1
            continue
        fi
        [ "$name" = cs40l26_input ] || continue
        found=$((found + 1))
        echo "INPUT=$input"
        timeout -s KILL 2 ls -ld "$input" "$input/device" "$input/device/driver"
        # A missing driver link is diagnostic only; the input may be virtual.
        case "$profile" in
            os4-current|os4-stable)
                for relative in default/vibe_state default/dsp_state default/fw_rev \
                    default/overprotection_gain calibration/f0_stored \
                    calibration/redc_stored calibration/q_stored; do
                    read_node "$input/$relative"
                done ;;
            *)
                echo "UNREVIEWED_PROFILE=$profile: skipping driver attribute reads."
                status=1 ;;
        esac
    done
    echo "MATCHING_INPUTS=$found"
    [ "$found" -gt 0 ] || status=1
} > "$out/haptics-state.txt" 2>&1

capture dmesg-after.txt dmesg
capture interrupts-after.txt cat /proc/interrupts
capture uptime-after.txt cat /proc/uptime
capture logcat.txt logcat -b all -d
capture threads.txt ps -AT
printf '%s\n' "$status" > "$out/collection-exit.txt"
echo "DONE: $out"
exit "$status"
