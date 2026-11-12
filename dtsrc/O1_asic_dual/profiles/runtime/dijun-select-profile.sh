#!/system/bin/sh
# Read-only preflight. Invoke only AFTER active-slot system/vendor/odm/vendor_dlkm
# mounts exist. This never mounts, inserts modules, changes properties or starts
# services. dijun-runtime.sh owns the separate activation transaction.
set -f
root=
profiles=/system/etc/dijun/profiles
blobs=/system/etc/dijun/blobs
while [ "$#" -gt 0 ]; do
    [ "$#" -ge 2 ] || { echo 'missing argument' >&2; exit 2; }
    case "$1" in
        --root) root=$2 ;;
        --profiles) profiles=$2 ;;
        --blobs) blobs=$2 ;;
        *) echo 'unknown argument' >&2; exit 2 ;;
    esac
    shift 2
done
[ "$root" != / ] || root=
case "$root" in ''|/*) ;; *) echo 'root must be absolute' >&2; exit 2 ;; esac
fail() { echo "profile preflight: $*" >&2; exit 2; }
kernel=$(cat "$root/proc/sys/kernel/osrelease") || fail 'kernel release unavailable'
[ -n "$kernel" ] || fail 'empty kernel release'
# Read bootloader evidence, not the recovery build identity that KeyMint may
# override later. Conflicting or absent slots never fall back to slot A.
slot=$(awk '
    /^[[:space:]]*androidboot[.]slot_suffix[[:space:]]*=/ {
        x=$0; sub(/^[^=]*=[[:space:]]*/, "", x); gsub(/["[:space:]]/, "", x);
        count++; value=x
    }
    END { if (count == 1) print value; else exit 1 }
' "$root/proc/bootconfig") || fail 'missing or ambiguous boot slot'
case "$slot" in _a|_b) ;; *) fail 'invalid boot slot' ;; esac

for partition in system vendor odm vendor_dlkm; do
    point=/$partition
    [ "$partition" != system ] || point=/system_root
    source=$(awk -v point="$point" '$2 == point { count++; source=$1 }
        END { if (count == 1) print source; else exit 1 }' "$root/proc/mounts") || fail "missing or ambiguous $point mount"
    case "$source" in /dev/block/dm-*) dm=${source##*/} ;; *) fail "unrecognized $point block source" ;; esac
    number=${dm#dm-}
    case "$number" in ''|*[!0-9]*) fail 'invalid mapper number' ;; esac
    name=$(cat "$root/sys/class/block/$dm/dm/name") || fail "missing mapper name for $point"
    [ "$name" = "$partition$slot" ] || fail "$point belongs to $name, expected $partition$slot"
done

file_hash() {
    [ -f "$1" ] && [ -r "$1" ] || return 1
    hash=$(sha256sum "$1") || return 1
    hash=${hash%% *}
    [ "${#hash}" -eq 64 ] || return 1
    printf '%s' "$hash"
}

matches() {
    schema=0; kernel_seen=0; identities='|'; blob_count=0
    while read -r kind one two three extra; do
        [ -z "$extra" ] || return 2
        case "$kind" in
            ''|'#'*) continue ;;
            schema)
                [ "$schema" -eq 0 ] && [ "$one" = 1 ] && [ -z "$two$three" ] || return 2
                schema=1 ;;
            kernel)
                [ "$kernel_seen" -eq 0 ] && [ -z "$two$three" ] || return 2
                kernel_seen=1
                [ "$one" = "$kernel" ] || { echo "$id: kernel release differs" >&2; return 1; } ;;
            identity)
                case "$identities" in *"|$one|"*) return 2 ;; esac
                case "$one:$three" in
                    system:/system_root/system/build.prop|vendor:/vendor/build.prop|odm:/odm/etc/build.prop|fstab:/vendor/etc/fstab.O1_asic|touch:/vendor_dlkm/lib/modules/synaptics_tcm2.ko|haptics:/vendor_dlkm/lib/modules/xring_smartpa.ko|haptics:/vendor_dlkm/lib/modules/xring_audio_hw_third.ko) ;;
                    *) return 2 ;;
                esac
                [ "${#two}" -eq 64 ] || return 2
                case "$two" in *[!0-9a-f]*) return 2 ;; esac
                observed=$(file_hash "$root$three") || { echo "$id: unavailable $one" >&2; return 1; }
                [ "$observed" = "$two" ] || { echo "$id: $one hash differs" >&2; return 1; }
                identities="$identities$one|" ;;
            blob)
                [ "${#one}" -eq 64 ] && [ -z "$three" ] || return 2
                case "$one" in *[!0-9a-f]*) return 2 ;; esac
                case "$two" in ''|*[!0-9]*) return 2 ;; esac
                observed=$(file_hash "$blobs/$one") || { echo "$id: missing blob $one" >&2; return 1; }
                [ "$observed" = "$one" ] || { echo "$id: corrupted blob $one" >&2; return 1; }
                size=$(wc -c < "$blobs/$one") || return 1
                [ "$size" -eq "$two" ] || return 1
                blob_count=$((blob_count + 1)) ;;
            *) return 2 ;;
        esac
    done < "$1"
    [ "$schema" -eq 1 ] && [ "$kernel_seen" -eq 1 ] && [ "$blob_count" -gt 0 ] || return 2
    for required in system vendor odm fstab touch haptics; do
        case "$identities" in *"|$required|"*) ;; *) return 2 ;; esac
    done
    return 0
}

count=0; chosen=
# Globbing is enabled only for this fixed catalog pattern, never manifest data.
set +f
for manifest in "$profiles"/*/selection.conf; do
    [ -f "$manifest" ] || continue
    dir=${manifest%/*}; id=${dir##*/}
    case "$id" in ''|*[!a-z0-9-]*) fail 'invalid profile id' ;; esac
    set -f
    matches "$manifest"
    result=$?
    case "$result" in
        0) count=$((count + 1)); chosen=$id ;;
        1) ;;
        *) fail "malformed profile: $id" ;;
    esac
done
[ "$count" -ne 0 ] || { echo 'profile preflight: no complete matching profile' >&2; exit 3; }
[ "$count" -eq 1 ] || { echo 'profile preflight: ambiguous catalog' >&2; exit 4; }
printf 'PROFILE=%s\nSLOT=%s\nKERNEL_RELEASE=%s\nSTATUS=matched-not-activated\n' "$chosen" "$slot" "$kernel"
