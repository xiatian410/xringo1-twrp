#!/system/bin/sh
# Called after a verified profile is published, before any HAL is started.
set -fu
root=
if [ "$#" -gt 0 ]; then
    [ "$#" -eq 2 ] && [ "$1" = --root ] || exit 2
    root=$2
    case "$root" in ''|/*) ;; *) exit 2 ;; esac
fi
exec >> "$root/tmp/dijun-mitee-prepare.log" 2>&1
[ -f "$root/tmp/dijun-runtime/published" ] || exit 1
setprop twrp.mitee.prepared 0
i=0
while [ ! -c "$root/dev/tee0" ] || [ ! -c "$root/dev/teepriv0" ]; do
    i=$((i + 1))
    [ "$i" -lt 50 ] || { echo 'TEE device nodes unavailable'; exit 1; }
    sleep 0.1
done
persist=$root/mnt/vendor/persist
mkdir -p "$persist" || exit 1
source=$(awk '$2 == "/mnt/vendor/persist" { count++; source=$1 }
    END { if (count > 1) exit 1; print source }' "$root/proc/mounts") || exit 1
if [ -n "$source" ]; then
    [ "$(readlink -f "$root$source")" = "$(readlink -f "$root/dev/block/by-name/persist")" ] || {
        echo 'Existing persist mount does not match original secure storage'; exit 1;
    }
else
    mount -t ext4 -o nosuid,nodev,noatime "$root/dev/block/by-name/persist" "$persist" || exit 1
fi
for d in "$persist/data" "$persist/fdsd"; do
    if [ ! -d "$d" ]; then mkdir -m 0755 "$d" && chown 1000:1000 "$d" || exit 1; fi
done
mkdir -p "$root/data/vendor/mitee" || exit 1
chmod 0775 "$root/data/vendor/mitee" && chown 1000:1000 "$root/data/vendor/mitee" || exit 1
for node in /dev/tee0 /dev/teepriv0 /dev/rpmb0 /dev/ufs-bsg0 /dev/0:0:0:49476; do
    [ -e "$root$node" ] || continue
    chmod 0600 "$root$node" && chown 1000:1000 "$root$node" || exit 1
done
[ ! -e "$root/dev/timestamp" ] || chmod 0444 "$root/dev/timestamp"
setprop vendor.teefs_state ready
setprop ro.hardware.gatekeeper mitee
setprop twrp.mitee.prepared 1
echo 'Matching MiTEE nodes and original persist storage prepared'
