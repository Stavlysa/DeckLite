#!/usr/bin/env bash

[[ -r /etc/profile.d/00-decklite-glibc-loader.sh ]] && \
    source /etc/profile.d/00-decklite-glibc-loader.sh

# The Hangover layer is assembled offline and can update libraries again on a
# later container start. Never trust a first-boot marker: refresh the loader
# cache before invoking sudo or Wine on every boot. ldconfig is statically
# linked, so it remains runnable even when the old cache maps libc.so.6 to the
# libc.so linker script.
if /sbin/ldconfig; then
    sudo touch /var/lib/decklite-hangover-ldconfig || true
else
    printf 'Warning: unable to rebuild the dynamic loader cache.\n' >&2
fi

# Warm wineserver must receive the same CPU policy as game launchers.
source /opt/tiny/wine-manager/wine-affinity-env.sh

# GLib/Exo needs the desktop MIME cache, not only a .desktop file. Keep the
# shipped first-boot cache current after users add or update application entries.
# This indexes handlers without overwriting users' preferred associations.
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" || true
fi

# Materialise the ready-to-play default prefix on first container start.  The
# template is part of the imported image, so this performs no network access.
if [[ ! -f /home/tiny/.wine/system.reg && \
      -f /opt/tiny/wine-manager/prefix-templates/game-complete/system.reg ]]; then
    nohup /opt/tiny/wine-manager/prepare-prefix.sh /home/tiny/.wine \
        >/home/tiny/wine-prefix-first-start.log 2>&1 </dev/null &
else
    # Keep the warmed server consistent without changing the desktop session.
    ( source /opt/tiny/wine-manager/wine-region-env.sh
      wineserver -p >/dev/null 2>&1 ) || true
fi
