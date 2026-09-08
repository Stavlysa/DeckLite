#!/usr/bin/env bash
# Source before Wine OR wineserver. Wine applies affinity in the persistent
# server, so preloading only the game process does not handle CPU-0 requests.
export DECKLITE_REMAP_CPU0="${DECKLITE_REMAP_CPU0:-1}"
# Include all available big/prime cores; leave Android's cpuset restrictions
# intact. Use "all" for the former unpinned policy, or REMAP_CPU0=0 to opt out.
if [[ -z "${DECKLITE_WINE_CPU_POLICY:-}" ]]; then
    cpu_preference=big
    cpu_preference_file="${XDG_CONFIG_HOME:-$HOME/.config}/decklite/wine-cpu-policy"
    if [[ -r "$cpu_preference_file" ]]; then
        IFS= read -r cpu_preference <"$cpu_preference_file" || true
    fi
    case "$cpu_preference" in
        big|all) export DECKLITE_WINE_CPU_POLICY="$cpu_preference" ;;
        custom:*)
            if [[ "${cpu_preference#custom:}" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
                export DECKLITE_WINE_CPU_POLICY=custom
                export DECKLITE_WINE_CPUS="${cpu_preference#custom:}"
            else
                export DECKLITE_WINE_CPU_POLICY=big
            fi
            ;;
        *) export DECKLITE_WINE_CPU_POLICY=big ;;
    esac
fi
affinity_shim=/opt/tiny/extra/libdecklite-affinity.so
if [[ -f "$affinity_shim" && ":${LD_PRELOAD:-}:" != *":$affinity_shim:"* ]]; then
    export LD_PRELOAD="$affinity_shim${LD_PRELOAD:+:$LD_PRELOAD}"
fi
