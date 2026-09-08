#!/usr/bin/env bash
# PRoot itself uses Tiny Container's Android/Bionic bootstrap libraries, but
# glibc applications inside the Debian guest must never search that directory.
# Filter it without executing an external command: external tools may already
# fail if the mixed Bionic/glibc path reached this profile.
case "${LD_LIBRARY_PATH:-}" in
    *"/files/bootstrap/lib"*)
        decklite_clean_ld_path=
        decklite_old_ifs=$IFS
        IFS=:
        for decklite_ld_entry in $LD_LIBRARY_PATH; do
            case "$decklite_ld_entry" in
                ""|*"/files/bootstrap/lib") continue ;;
            esac
            decklite_clean_ld_path="${decklite_clean_ld_path:+$decklite_clean_ld_path:}$decklite_ld_entry"
        done
        IFS=$decklite_old_ifs
        export LD_LIBRARY_PATH="${decklite_clean_ld_path:-/lib/aarch64-linux-gnu:/usr/lib/aarch64-linux-gnu:/lib:/usr/lib}"
        unset decklite_clean_ld_path decklite_old_ifs decklite_ld_entry
        ;;
esac
