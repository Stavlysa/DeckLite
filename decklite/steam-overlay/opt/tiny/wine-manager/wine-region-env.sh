#!/usr/bin/env bash
# Source only in Wine launchers, never in the desktop/Steam session profile.
# Read allow-listed data, not executable shell configuration. No subprocesses.
decklite_wine_region_env() {
    local config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/decklite"
    local locale="${DECKLITE_WINE_LOCALE:-}" language offset tz magnitude sign
    if [[ -z "$locale" && -r "$config_dir/wine-locale" ]]; then
        IFS= read -r locale <"$config_dir/wine-locale" || true
    fi
    locale="${locale%$'\r'}"
    case "$locale" in
        zh_TW.UTF-8) language="zh_TW:zh:en" ;;
        zh_CN.UTF-8) language="zh_CN:zh:en" ;;
        ja_JP.UTF-8) language="ja_JP:ja:en" ;;
        ru_RU.UTF-8) language="ru_RU:ru:en" ;;
        *) locale="en_US.UTF-8"; language="en_US:en" ;;
    esac
    offset="${DECKLITE_WINE_UTC_OFFSET:-}"
    if [[ -z "$offset" && -r "$config_dir/wine-timezone" ]]; then
        IFS= read -r offset <"$config_dir/wine-timezone" || true
    fi
    offset="${offset%$'\r'}"
    # Must match wine_timezone.py. Validate BEFORE shell arithmetic.
    case "$offset" in
        -720|-660|-600|-570|-540|-480|-420|-360|-300|-240|-210|-180|-120|-60|0|60|120|180|210|240|270|300|330|345|360|390|420|480|525|540|570|600|630|660|720|765|780|840) ;;
        *) offset=0 ;;
    esac
    if (( offset == 0 )); then
        tz=UTC0
    else
        magnitude="${offset#-}"
        if [[ $offset == -* ]]; then sign=+; else sign=-; fi
        printf -v tz 'UTC%s%d:%02d' "$sign" \
            "$((magnitude / 60))" "$((magnitude % 60))"
    fi
    export DECKLITE_WINE_LOCALE="$locale" LANG="$locale" LC_ALL="$locale" LANGUAGE="$language"
    export DECKLITE_WINE_UTC_OFFSET="$offset" TZ="$tz"
}
decklite_wine_region_env
unset -f decklite_wine_region_env
