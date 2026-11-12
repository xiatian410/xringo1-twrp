#!/system/bin/sh
# Read-only emergency snapshot. No mounts, size walks, writes to sysfs or signalling.
echo '=== UPTIME ==='
cat /proc/uptime
echo '=== RECOVERY TASKS ==='
for recovery_pid in $(pidof recovery); do
    echo "RECOVERY_PID=$recovery_pid"
    echo '=== DESCRIPTORS ==='
    ls -l "/proc/$recovery_pid/fd"
    for task in /proc/"$recovery_pid"/task/*; do
        [ -d "$task" ] || continue
        echo "=== THREAD $task ==="
        for field in comm status wchan stack syscall; do
            echo "--- $field ---"
            if command -v timeout >/dev/null 2>&1; then
                timeout -s KILL 2 cat "$task/$field"
            else
                cat "$task/$field"
            fi
        done
    done
done
echo '=== THREAD/CHILD PROCESS LIST ==='
ps -AT
echo '=== MOUNTS ==='
cat /proc/mounts
echo '=== MOUNTINFO ==='
cat /proc/self/mountinfo
echo '=== IO PRESSURE ==='
cat /proc/pressure/io
