#!/system/bin/sh
# Read-only kernel/input observations. Writes collected output only under /tmp.
# Do not reset the controller, change report mode, or unload drivers here.
set -u
out=/tmp/dijun-touch-no-events
mkdir -p "$out" || exit 1
if ! command -v timeout >/dev/null 2>&1; then
    echo 'Missing timeout; collection stopped before starting getevent.' >&2
    exit 1
fi

snapshot() {
    phase=$1
    cat /proc/uptime > "$out/$phase-uptime.txt"
    cat /proc/interrupts > "$out/$phase-interrupts.txt"
    {
        for irq in $(awk '/xiaomi_tpsynaptics_tcm/ {gsub(":", "", $1); print $1}' /proc/interrupts); do
            echo "IRQ=$irq"
            for node in /proc/irq/"$irq"/spurious /sys/kernel/irq/"$irq"/actions \
                /sys/kernel/irq/"$irq"/chip_name /sys/kernel/irq/"$irq"/hwirq \
                /sys/kernel/irq/"$irq"/type /sys/kernel/irq/"$irq"/wakeup \
                /sys/kernel/debug/irq/irqs/"$irq"; do
                if [ -r "$node" ]; then
                    echo "--- $node"
                    cat "$node"
                fi
            done
        done
    } > "$out/$phase-irq-state.txt" 2>&1
}

controller_info() {
    phase=$1
    # Only the cached info show callback was inspected in both OS4 modules.
    # Reading testing/*, reset, raw frames or arbitrary sysfs files may send
    # controller commands; do not recursively read the driver directory.
    {
        found=0
        for node in /sys/bus/platform/devices/synaptics_tcm*/synaptics_tcm/info \
                    /sys/bus/spi/devices/*/synaptics_tcm/info; do
            [ -r "$node" ] || continue
            found=1
            echo "--- $node"
            timeout -s KILL 2 cat "$node"
            echo "READ_EXIT=$?"
        done
        [ "$found" = 1 ] || echo 'Cached Synaptics info node not found at inspected paths.'
    } > "$out/$phase-controller-info.txt" 2>&1
}

date > "$out/date.txt"
getprop > "$out/getprop.txt"
cat /proc/modules > "$out/modules.txt"
cat /proc/bus/input/devices > "$out/input-devices.txt"
getevent -pl > "$out/getevent-devices.txt" 2>&1
{
    cat /sys/module/firmware_class/parameters/path
    for module in synaptics_tcm2 xiaomi_touch_dijun tui xr_spi_mmio shub_ipc_drv; do
        echo "--- $module"
        cat /sys/module/"$module"/initstate
    done
    ls -l /sys/bus/spi/devices/*/driver
    ls -l /lib/firmware/synaptics_spi_dijun.img
    for node in /sys/class/backlight/*/brightness /sys/class/backlight/*/bl_power; do
        if [ -r "$node" ]; then echo "--- $node"; cat "$node"; fi
    done
} > "$out/state.txt" 2>&1
dmesg > "$out/dmesg-before.txt" 2>&1
controller_info before
echo 'IDLE: 4 seconds. Keep the screen on and do not touch it.'
snapshot idle-start
timeout -s KILL 4 getevent -lt > "$out/idle-events.txt" 2>&1
echo "$?" > "$out/idle-getevent-exit.txt"
snapshot idle-end
echo 'TOUCH: 12 seconds. Continuously swipe the screen now; do not press power.'
snapshot touch-start
timeout -s KILL 12 getevent -lt > "$out/touch-events.txt" 2>&1
echo "$?" > "$out/touch-getevent-exit.txt"
snapshot touch-end
controller_info after
dmesg > "$out/dmesg-after.txt" 2>&1
logcat -b all -d > "$out/logcat.txt" 2>&1
ps -AT > "$out/threads.txt" 2>&1
for source in /tmp/recovery.log /tmp/dijun-runtime.log; do
    if [ -r "$source" ]; then cp "$source" "$out/"; fi
done
{
    echo 'Cumulative IRQ snapshots; compare per-second idle and touch deltas.'
    for phase in idle-start idle-end touch-start touch-end; do
        echo "--- $phase"
        cat "$out/$phase-uptime.txt"
        grep -E 'xiaomi_tpsynaptics_tcm|spi_dma_irq|e1507000.spi' "$out/$phase-interrupts.txt"
    done
    echo '--- input event line counts (all devices; inspect device and type)'
    grep -c 'EV_' "$out/idle-events.txt"
    grep -c 'EV_' "$out/touch-events.txt"
    echo 'A timeout/KILL exit after each collection window is expected.'
    echo 'No-event observations do not identify a unique controller/driver failure.'
} > "$out/summary.txt"
cat "$out/summary.txt"
echo "DONE: $out"
