#!/system/bin/sh
# Recovery consumes ordinary coordinates, not Android's userspace THP frames.
# Caller bounds this whole operation with timeout: sysfs may wait on hardware.
set -fu
root=${1:-}
case "$root" in ''|/*) ;; *) exit 2 ;; esac
[ "$root" != / ] || root=
node=$root/sys/class/touch/touch_dev/enable_touch_raw
tries=0
while :; do
    state=$(cat "$root/sys/module/synaptics_tcm2/initstate" 2>/dev/null) || state=
    if [ "$state" = live ] && [ -w "$node" ] &&
       grep -Fq 'Name="Xiaomi_Touch_Input_0"' "$root/proc/bus/input/devices" 2>/dev/null; then
        break
    fi
    [ "$tries" -lt 20 ] || { echo 'touch reports: panel/input not available'; exit 1; }
    sleep 0.1
    tries=$((tries + 1))
done
# synaptics_tcm2 queues a 50-jiffy worker during connect. On the stable OS4
# driver it can switch back to raw reports, so let that probe work settle before
# making the final Recovery-mode request. This is deliberately bounded.
sleep 2
state=$(cat "$root/sys/module/synaptics_tcm2/initstate" 2>/dev/null) || state=
if [ "$state" != live ] || ! grep -Fq 'Name="Xiaomi_Touch_Input_0"' "$root/proc/bus/input/devices" 2>/dev/null; then
    echo 'touch reports: panel/input disappeared during settle window'
    exit 1
fi
# Always issue the request: the wrapper cache is not a controller query.
# Do not reset/reflash the controller or change calibration here.
printf '0\n' > "$node" || { echo 'touch reports: ordinary-report request failed'; exit 1; }
value=$(cat "$node") || exit 1
[ "$value" = 0 ] || { echo 'touch reports: raw cache did not become zero'; exit 1; }
echo 'touch reports: ordinary reports requested; cache=0 (event delivery not tested)'
