#!/usr/bin/env bash
set -Eeuo pipefail

if (( EUID != 0 )); then
    echo "The Tiny Container export command must run this script as root." >&2
    exit 1
fi

output=/Public/rootfs.tar.zst
rm -f "$output"

pacman -Scc --noconfirm >/dev/null 2>&1 || true
find /var/log -mindepth 1 -maxdepth 1 -type f -delete 2>/dev/null || true
rm -f /etc/ssh/ssh_host_* /var/lib/systemd/random-seed
: >/etc/machine-id

cd /
entries=(.tiny.yaml)
for path in bin etc home lib lib64 media mnt opt root sbin srv usr var; do
    [[ -e "$path" || -L "$path" ]] && entries+=("$path")
done

pseudo_entries=()
for path in \
    sys/fs/selinux \
    proc/loadavg \
    proc/stat \
    proc/uptime \
    proc/version \
    proc/vmstat \
    proc/bus/pci/devices \
    proc/sys/kernel/cap_last_cap \
    proc/sys/kernel/overflowuid \
    proc/sys/kernel/overflowgid \
    proc/sys/fs/inotify/max_user_watches; do
    [[ -e "$path" ]] && pseudo_entries+=("$path")
done

tar --zstd -cpf "$output" \
    --exclude='home/alarm/.cache/*' \
    --exclude='home/alarm/.bash_history' \
    --exclude='home/alarm/.zsh_history' \
    --exclude='home/alarm/.ssh/*' \
    --exclude='home/alarm/.gnupg/*' \
    --exclude='home/alarm/.local/share/Steam/config/*' \
    --exclude='home/alarm/.local/share/Steam/userdata/*' \
    --exclude='var/cache/pacman/pkg/*' \
    --transform='s|^sys/fs/selinux$|sys/.empty|' \
    --transform='s|^proc/loadavg$|proc/.loadavg|' \
    --transform='s|^proc/stat$|proc/.stat|' \
    --transform='s|^proc/uptime$|proc/.uptime|' \
    --transform='s|^proc/version$|proc/.version|' \
    --transform='s|^proc/vmstat$|proc/.vmstat|' \
    --transform='s|^proc/bus/pci/devices$|proc/.devices|' \
    --transform='s|^proc/sys/kernel/cap_last_cap$|proc/.sysctl_entry_cap_last_cap|' \
    --transform='s|^proc/sys/kernel/overflowuid$|proc/.overflowuid|' \
    --transform='s|^proc/sys/kernel/overflowgid$|proc/.overflowgid|' \
    --transform='s|^proc/sys/fs/inotify/max_user_watches$|proc/.sysctl_inotify_max_user_watches|' \
    "${entries[@]}" "${pseudo_entries[@]}"

echo "Exported $output"
