#!/system/bin/sh
# Read-only preflight. Invoke only AFTER active-slot system/vendor/odm/vendor_dlkm
# mounts exist. This never mounts, inserts modules, changes properties or starts
# services. dijun-runtime.sh owns the separate activation transaction.
set -f
root=
profiles=/system/etc/dijun/profiles
blobs=/system/etc/dijun/blobs
purpose=full
while [ "$#" -gt 0 ]; do
    [ "$#" -ge 2 ] || { echo 'missing argument' >&2; exit 2; }
    case "$1" in
        --root) root=$2 ;;
        --profiles) profiles=$2 ;;
        --blobs) blobs=$2 ;;
        --purpose) purpose=$2 ;;
        *) echo 'unknown argument' >&2; exit 2 ;;
    esac
    shift 2
done
[ "$root" != / ] || root=
case "$root" in ''|/*) ;; *) echo 'root must be absolute' >&2; exit 2 ;; esac
fail() { echo "profile preflight: $*" >&2; exit 2; }
case "$purpose" in full|touch|haptics|crypto) ;; *) fail 'invalid purpose' ;; esac
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

component_matches() {
    # Validate only this component's hard closure. Loaded module sources are
    # checked too; neither module directory presence nor build labels prove ABI.
    seen='|'; module_count=0
    [ -s "$dir/$purpose-modules.plan" ] && [ -s "$dir/$purpose-files.list" ] &&
        [ -s "$dir/$purpose-checks.list" ] || return 2
    while read -r name sha path deps extra; do
        [ -z "$extra" ] || return 2
        case "$name" in ''|*[!a-zA-Z0-9_]*) return 2 ;; esac
        case "$seen" in *"|$name|"*) return 2 ;; esac
        [ "${#sha}" -eq 64 ] || return 2
        case "$sha" in *[!0-9a-f]*) return 2 ;; esac
        case "$path" in /lib/modules/*.ko|/vendor_dlkm/lib/modules/*.ko|/system_dlkm/lib/modules/*.ko) ;; *) return 2 ;; esac
        case "$path" in *..*|*[!a-zA-Z0-9_./+-]*) return 2 ;; esac
        case "$deps" in ''|*[!a-zA-Z0-9_,-]*) return 2 ;; esac
        if [ "$deps" != - ]; then
            oldifs=$IFS; IFS=,
            for dep in $deps; do
                case "$seen" in *"|$dep|"*) ;; *) IFS=$oldifs; return 2 ;; esac
            done
            IFS=$oldifs
        fi
        observed=$(file_hash "$root$path") || { echo "$id: $purpose dependency unavailable: $name" >&2; return 1; }
        [ "$observed" = "$sha" ] || { echo "$id: $purpose dependency hash differs: $name" >&2; return 1; }
        seen="$seen$name|"; module_count=$((module_count + 1))
    done < "$dir/$purpose-modules.plan"
    case "$purpose:$seen" in
        touch:*'|synaptics_tcm2|'*) ;;
        haptics:*'|xring_smartpa|'*|haptics:*'|xring_audio_hw_third|'*) ;;
        crypto:*'|fbe|'*)
            for required in mitee xr_ufs xr_rpmb; do
                case "$seen" in *"|$required|"*) ;; *) return 2 ;; esac
            done ;;
        *) return 2 ;;
    esac
    checked='|'
    while read -r sha path extra; do
        [ -z "$extra" ] && [ "${#sha}" -eq 64 ] || return 2
        case "$sha" in *[!0-9a-f]*) return 2 ;; esac
        case "$path" in *..*|*[!a-zA-Z0-9_./@+-]*) return 2 ;; esac
        case "$purpose:$path" in
            touch:/odm/firmware/synaptics_spi_dijun.img|touch:/odm/firmware/dijun_syna_thp_config.ini|            haptics:/odm/firmware/cs40l26*|haptics:/vendor/firmware/cs40l26*|            crypto:/vendor/bin/*|crypto:/vendor/lib64/*|crypto:/vendor/mitee/ta/*|crypto:/vendor/etc/vintf/manifest/*) ;;
            *) return 2 ;;
        esac
        case "$checked" in *"|$path|"*) return 2 ;; esac
        observed=$(file_hash "$root$path") || { echo "$id: $purpose component unavailable: $path" >&2; return 1; }
        [ "$observed" = "$sha" ] || { echo "$id: $purpose component hash differs: $path" >&2; return 1; }
        checked="$checked$path|"
    done < "$dir/$purpose-checks.list"
    files='|'; asset_count=0
    while read -r sha mode path extra; do
        [ -z "$extra" ] && [ "${#sha}" -eq 64 ] || return 2
        case "$sha" in *[!0-9a-f]*) return 2 ;; esac
        case "$mode" in 0644|0755) ;; *) return 2 ;; esac
        case "$path" in *..*|*[!a-zA-Z0-9_./@+-]*) return 2 ;; esac
        case "$purpose:$path" in
            touch:/lib/firmware/synaptics_spi_dijun.img|touch:/lib/firmware/dijun_syna_thp_config.ini|            haptics:/lib/firmware/cs40l26*|haptics:/vendor/firmware/cs40l26*|            crypto:/vendor/bin/*|crypto:/vendor/mitee/ta/*|crypto:/system/lib64/mitee/*) ;;
            *) return 2 ;;
        esac
        case "$files" in *"|$path|"*) return 2 ;; esac
        observed=$(file_hash "$blobs/$sha") || return 1
        [ "$observed" = "$sha" ] || return 1
        files="$files$path|"; asset_count=$((asset_count + 1))
    done < "$dir/$purpose-files.list"
    [ "$asset_count" -gt 0 ] || return 2
    if [ "$purpose" = touch ]; then [ "$asset_count" -eq 2 ] || return 2; fi
    if [ "$purpose" = crypto ]; then crypto_identity || return $?; fi
}

read_property() {
    # Android property files are data, never shell input. Reject duplicates,
    # empty values and whitespace; do not consult recovery's own getprop values.
    awk -v key="$2" '
        /^[[:space:]]*#/ { next }
        index($0, "=") {
            k=substr($0,1,index($0,"=")-1); gsub(/^[[:space:]]+|[[:space:]]+$/, "", k)
            if(k == key) { value=substr($0,index($0,"=")+1); sub(/\r$/, "", value); count++ }
        }
        END { if(count == 1 && value != "" && value !~ /[[:space:]]/) print value; else exit 1 }
    ' "$1"
}
valid_date() {
    # Gregorian date validation, independent of recovery timezone/clock state.
    printf '%s\n' "$1" | awk -F- '
        /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/ {
            y=$1+0; m=$2+0; d=$3+0; n=31
            if(m == 4 || m == 6 || m == 9 || m == 11) n=30
            if(m == 2) n=28+(y%4 == 0 && (y%100 != 0 || y%400 == 0))
            if(y >= 2000 && m >= 1 && m <= 12 && d >= 1 && d <= n) good=1
        } END { exit !good }'
}
crypto_identity() {
    release=$(read_property "$root/system_root/system/build.prop" ro.build.version.release) || { echo "$id: current Android release unavailable" >&2; return 1; }
    expected_release=$(cat "$dir/crypto-release.conf") || return 2
    [ "$release" = "$expected_release" ] || { echo "$id: unsupported Android release family" >&2; return 1; }
    system_spl=$(read_property "$root/system_root/system/build.prop" ro.build.version.security_patch) || return 1
    vendor_spl=$(read_property "$root/vendor/build.prop" ro.vendor.build.security_patch) || return 1
    valid_date "$system_spl" && valid_date "$vendor_spl" || { echo "$id: invalid current patch level" >&2; return 1; }
    # Compare the actual crypto/storage layout semantically. OTA comments,
    # unrelated mounts and flag ordering are not crypto compatibility changes.
    layout=$(awk '
        /^[[:space:]]*#/ { next }
        $2 == "/data" || $2 == "/metadata" || $2 == "/mnt/vendor/persist" {
            if(NF != 5) exit 1
            print $1, $2, $3, $4, $5; count++
        } END { if(count != 3) exit 1 }' "$root/vendor/etc/fstab.O1_asic") || return 1
    normalized=$(printf '%s\n' "$layout" | while read -r dev point fs mountflags flags; do
        mountflags=$(printf '%s' "$mountflags" | tr ',' '\n' | sort -u | paste -sd, -)
        flags=$(printf '%s' "$flags" | tr ',' '\n' | sort -u | paste -sd, -)
        printf '%s %s %s %s %s\n' "$dev" "$point" "$fs" "$mountflags" "$flags"
    done | sort) || return 1
    [ "$normalized" = "$(cat "$dir/crypto-layout.conf")" ] || { echo "$id: crypto storage layout differs" >&2; return 1; }
    echo "$id: component-compatible crypto; current Android=$release system_spl=$system_spl vendor_spl=$vendor_spl" >&2
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
                if [ "$purpose" = full ]; then
                    observed=$(file_hash "$root$three") || { echo "$id: unavailable $one" >&2; return 1; }
                    [ "$observed" = "$two" ] || { echo "$id: $one hash differs" >&2; return 1; }
                fi
                identities="$identities$one|" ;;
            blob)
                [ "${#one}" -eq 64 ] && [ -z "$three" ] || return 2
                case "$one" in *[!0-9a-f]*) return 2 ;; esac
                case "$two" in ''|*[!0-9]*) return 2 ;; esac
                if [ "$purpose" = full ]; then
                    observed=$(file_hash "$blobs/$one") || { echo "$id: missing blob $one" >&2; return 1; }
                    [ "$observed" = "$one" ] || { echo "$id: corrupted blob $one" >&2; return 1; }
                    size=$(wc -c < "$blobs/$one") || return 1
                    [ "$size" -eq "$two" ] || return 1
                fi
                blob_count=$((blob_count + 1)) ;;
            *) return 2 ;;
        esac
    done < "$1"
    [ "$schema" -eq 1 ] && [ "$kernel_seen" -eq 1 ] && [ "$blob_count" -gt 0 ] || return 2
    for required in system vendor odm fstab touch haptics; do
        case "$identities" in *"|$required|"*) ;; *) return 2 ;; esac
    done
    if [ "$purpose" != full ]; then component_matches; return $?; fi
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
        0) count=$((count + 1)); chosen=$id; chosen_release=${release:-}; chosen_system_spl=${system_spl:-}; chosen_vendor_spl=${vendor_spl:-} ;;
        1) ;;
        *) fail "malformed profile: $id" ;;
    esac
done
[ "$count" -ne 0 ] || { echo 'profile preflight: no complete matching profile' >&2; exit 3; }
[ "$count" -eq 1 ] || { echo 'profile preflight: ambiguous catalog' >&2; exit 4; }
printf 'PROFILE=%s\nSLOT=%s\nKERNEL_RELEASE=%s\nSTATUS=matched-not-activated\nPURPOSE=%s\n' "$chosen" "$slot" "$kernel" "$purpose"

if [ "$purpose" = crypto ]; then
    printf 'ANDROID_RELEASE=%s\nSYSTEM_SPL=%s\nVENDOR_SPL=%s\n' "$chosen_release" "$chosen_system_spl" "$chosen_vendor_spl"
fi
