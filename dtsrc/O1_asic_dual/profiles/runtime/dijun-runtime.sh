#!/system/bin/sh
# Three phases, called by recovery: cache while stock partitions are mounted;
# modules after all bytes pass verification; publish after startup unmounts.
# --root redirects file operations for host fixtures, never enabled by init.
set -fu
phase=${1:-}; shift || exit 2
root=
if [ "$#" -gt 0 ]; then
    [ "$#" -eq 2 ] && [ "$1" = --root ] || exit 2
    root=$2
    case "$root" in /*) ;; *) exit 2 ;; esac
    [ "$root" != / ] || root=
fi
catalog=$root/system/etc/dijun/profiles
blobs=$root/system/etc/dijun/blobs
stage=$root/tmp/dijun-runtime
started=0
mkdir -p "$root/tmp" || exit 1
exec >> "$root/tmp/dijun-runtime.log" 2>&1
fail() {
    echo "runtime $phase: $*"
    if [ "$started" = 1 ]; then
        for service in dijun-gatekeeper dijun-keymint dijun-tee-supplicant; do setprop ctl.stop "$service"; done
    fi
    setprop twrp.crypto.ready 0
    setprop twrp.profile.state failed
    exit 1
}
hash_ok() {
    [ -f "$1" ] && [ ! -L "$1" ] || return 1
    observed=$(sha256sum "$1") || return 1
    [ "${observed%% *}" = "$2" ]
}
safe_target() {
    case "$1" in /*) ;; *) return 1 ;; esac
    case "$1" in *'/../'*|*/..|*'/./'*|*//*|*[!a-zA-Z0-9_./@+-]*) return 1 ;; esac
    check=$root$1
    while [ "$check" != "$root" ] && [ "$check" != / ]; do
        [ ! -L "$check" ] || return 1
        check=${check%/*}
    done
}
copy_checked() {
    src=$1; dest=$2; sha=$3; mode=$4
    hash_ok "$src" "$sha" || return 1
    mkdir -p "${dest%/*}" && cp "$src" "$dest" && chmod "$mode" "$dest" || return 1
    hash_ok "$dest" "$sha"
}
check_unmounted() {
    # Publishing must never write through a mounted stock system/vendor/ODM.
    awk '$2 == "/vendor" || $2 == "/odm" || $2 == "/system" ||
         $2 == "/system_root" || $2 == "/system_ext" { bad=1 }
         END { exit bad }' "$root/proc/mounts"
}
module_live() {
    # Planned entries are loadable .ko files, not built-ins. Their directory
    # exists before module_init finishes, and can survive during teardown.
    module_state=$(cat "$root/sys/module/$1/initstate" 2>/dev/null) || return 1
    [ "$module_state" = live ]
}
haptics_input_registered() {
    [ -r "$root/proc/bus/input/devices" ] &&
        grep -Fq 'Name="cs40l26_input"' "$root/proc/bus/input/devices"
}
wait_haptics_input() {
    tries=0
    while [ "$tries" -lt 10 ]; do
        haptics_input_registered && return 0
        sleep 0.1
        tries=$((tries + 1))
    done
    haptics_input_registered
}
wait_module_live() {
    tries=0
    while [ "$tries" -lt 20 ]; do
        module_live "$1" && return 0
        # Only an observed 'coming' state can advance without intervention.
        [ "$module_state" = coming ] || return 1
        sleep 0.1
        tries=$((tries + 1))
    done
    module_live "$1"
}
case "$phase" in
cache)
    setprop twrp.crypto.ready 0
    setprop twrp.profile.state selecting
    [ ! -e "$stage" ] || fail 'already staged; refusing a second activation in one boot'
    mkdir -m 0700 "$stage" || fail 'cannot create private staging directory'
    sh "$root/system/bin/dijun-select-profile.sh" --root "$root" \
        --profiles "$catalog" --blobs "$blobs" > "$stage/selection" || fail 'no verified profile'
    profile=$(sed -n 's/^PROFILE=//p' "$stage/selection")
    case "$profile" in os2-initial|os2-final|os3-initial|os3-final|os4-current|os4-stable) ;; *) fail 'invalid selection' ;; esac
    source=$catalog/$profile
    cp "$source/runtime-files.list" "$stage/files" || fail 'missing asset list'
    cp "$source/modules.plan" "$stage/modules.plan" || fail 'missing module plan'
    cp "$source/crypto.prop" "$stage/crypto.prop" || fail 'missing crypto identity'
    while read -r sha mode path extra; do
        [ -z "$extra" ] || fail 'malformed asset line'
        case "$mode" in 0644|0755) ;; *) fail 'invalid mode' ;; esac
        case "$path" in /vendor/bin/*|/vendor/mitee/ta/*|/vendor/firmware/*|/lib/firmware/*|/system/lib64/mitee/*) ;; *) fail 'invalid asset destination' ;; esac
        safe_target "$path" || fail 'unsafe asset path'
        copy_checked "$blobs/$sha" "$stage/root$path" "$sha" "$mode" || fail "asset copy $path"
    done < "$stage/files"
    [ -d "$root/sys/module" ] || fail 'loaded-module evidence unavailable'
    mkdir "$stage/modules" || fail 'cannot stage modules'
    while read -r name sha path deps extra; do
        [ -z "$extra" ] || fail 'malformed module line'
        case "$name" in ''|*[!a-zA-Z0-9_]*) fail 'invalid module name' ;; esac
        case "$path" in /lib/modules/*.ko|/vendor_dlkm/lib/modules/*.ko|/system_dlkm/lib/modules/*.ko) ;; *) fail 'invalid module source' ;; esac
        module_live "$name" && continue
        copy_checked "$root$path" "$stage/modules/$name.ko" "$sha" 0644 || fail "missing or mismatched module $name"
    done < "$stage/modules.plan"
    # All inputs passed; only now make matching firmware visible to drivers.
    while read -r sha mode path; do
        case "$path" in /lib/firmware/*)
            safe_target "$path" || fail 'firmware path changed'
            copy_checked "$stage/root$path" "$root$path" "$sha" "$mode" || fail "firmware $path" ;;
        esac
    done < "$stage/files"
    printf '%s\n' /lib/firmware > "$root/sys/module/firmware_class/parameters/path" || fail 'firmware path unavailable'
    printf '%s\n' "$profile" > "$stage/profile"
    touch "$stage/cached"
    setprop twrp.profile.selected "$profile"
    setprop twrp.profile.state cached
    echo "runtime cache: verified $profile"
    ;;
modules)
    [ -f "$stage/cached" ] || fail 'cache incomplete'
    result=complete
    setprop twrp.profile.touch_modules pending
    setprop twrp.profile.modules pending
    setprop twrp.profile.haptics_input pending
    while read -r name sha path deps; do
        if [ -d "$root/sys/module/$name" ]; then
            if wait_module_live "$name"; then
                [ "$name" != synaptics_tcm2 ] || setprop twrp.profile.touch_modules loaded
            else
                echo "runtime module: existing $name is not live (state=${module_state:-unavailable}); no reinsertion"
                result=partial
                [ "$name" != synaptics_tcm2 ] || setprop twrp.profile.touch_modules failed
            fi
            continue
        fi
        ready=1
        if [ "$deps" != - ]; then
            oldifs=$IFS; IFS=,
            for dep in $deps; do module_live "$dep" || ready=0; done
            IFS=$oldifs
        fi
        if [ "$ready" = 0 ]; then
            echo "runtime module: skipped $name, hard dependency unavailable"
            [ "$name" != synaptics_tcm2 ] || setprop twrp.profile.touch_modules failed
            result=partial; continue
        fi
        hash_ok "$stage/modules/$name.ko" "$sha" || fail "staged module changed: $name"
        echo "runtime module: inserting $name"
        if ! timeout -s KILL 8 insmod "$stage/modules/$name.ko"; then
            echo "runtime module: insertion failed: $name"
            result=partial
        fi
        if ! wait_module_live "$name"; then
            echo "runtime module: $name did not become live (state=${module_state:-unavailable})"
            result=partial
        fi
        if [ "$name" = synaptics_tcm2 ]; then
            if module_live "$name"; then
                setprop twrp.profile.touch_modules loaded
            else
                setprop twrp.profile.touch_modules failed
            fi
        fi
    done < "$stage/modules.plan"
    # Panel setup can finish asynchronously after module_init. Request ordinary
    # reports only after the actual Xiaomi input registration has appeared.
    # A successful sysfs write is not controller/event readiness evidence.
    setprop twrp.profile.touch_reports pending
    if timeout -s KILL 6 sh "$root/system/bin/dijun-touch-reports.sh" "$root"; then
        setprop twrp.profile.touch_reports requested
    else
        setprop twrp.profile.touch_reports request_failed
        echo 'runtime touch: ordinary-report request unavailable or failed'
    fi
    haptics_module=
    while read -r name sha path deps; do
        case "$name" in xring_smartpa|xring_audio_hw_third) haptics_module=$name ;; esac
    done < "$stage/modules.plan"
    if [ -n "$haptics_module" ] && module_live "$haptics_module" && wait_haptics_input; then
        setprop twrp.profile.haptics_input registered
    else
        setprop twrp.profile.haptics_input not_registered
    fi
    echo "runtime haptics input: $(getprop twrp.profile.haptics_input) (input registration only; FF capability not tested)"
    # Module presence is only one layer: preserve registration evidence too.
    # Input names/capabilities do not contain credentials or filesystem keys.
    if [ -r "$root/proc/bus/input/devices" ]; then
        echo 'runtime input registration snapshot (not an event-delivery test):'
        cat "$root/proc/bus/input/devices"
    fi
    setprop twrp.profile.modules "$result"
    echo "runtime modules: $result"
    ;;
publish)
    [ -f "$stage/cached" ] || fail 'no cached profile'
    [ ! -f "$stage/published" ] || fail 'already published'
    check_unmounted || fail 'stock partitions still mounted'
    # Check the full set before touching any live runtime file.
    while read -r sha mode path; do
        safe_target "$path" && hash_ok "$stage/root$path" "$sha" || fail "changed cached asset $path"
    done < "$stage/files"
    while read -r sha mode path; do
        copy_checked "$stage/root$path" "$root$path" "$sha" "$mode" || fail "publish $path"
    done < "$stage/files"
    count=0
    while IFS='=' read -r key value; do
        case "$key" in ro.build.version.release|ro.build.version.security_patch|ro.vendor.build.security_patch) ;; *) fail 'unexpected crypto property' ;; esac
        case "$value" in ''|*[!0-9.-]*) fail 'invalid crypto identity' ;; esac
        resetprop -n "$key" "$value" || fail 'crypto property write failed'
        [ "$(getprop "$key")" = "$value" ] || fail 'crypto identity readback differs'
        count=$((count + 1))
    done < "$stage/crypto.prop"
    [ "$count" -eq 3 ] || fail 'incomplete crypto identity'
    touch "$stage/published"
    setprop twrp.profile.state published
    if [ "$(getprop ro.boot.mitee_disable)" = true ]; then
        echo 'runtime publish: MiTEE disabled by boot configuration'
        exit 0
    fi
    timeout -s KILL 8 sh "$root/system/bin/dijun-prepare-mitee.sh" --root "$root" || fail 'MiTEE prerequisites unavailable'
    # Explicit startup only; init has no lazy interface trigger for these HALs.
    started=1
    for service in dijun-tee-supplicant dijun-keymint dijun-gatekeeper; do
        setprop ctl.start "$service" || fail 'HAL start request failed'
    done
    if ! timeout -s KILL 18 "$root/system/bin/dijun-wait-services"; then
        fail 'HAL registration did not become ready within deadline'
    fi
    setprop twrp.crypto.ready 1
    setprop twrp.profile.state ready
    echo 'runtime publish: matching HAL interfaces registered; hardware key operations not yet tested'
    ;;
*) fail 'expected cache, modules or publish' ;;
esac
