#!/usr/bin/env bash
set -Eeuo pipefail

if (( EUID != 0 )); then
    echo "Run as root: su -c '/opt/tiny/setup-desktop.sh'" >&2
    exit 1
fi

echo "[1/5] Initialising the Arch Linux ARM package keyring..."
pacman-key --init
pacman-key --populate archlinuxarm

echo "[2/5] Updating the base userspace..."
pacman -Syu --noconfirm

echo "[3/5] Installing the lightweight desktop layer..."
packages=(
    sudo
    openbox
    tint2
    pcmanfm-gtk3
    lxterminal
    dbus
    xorg-xauth
    xorg-xsetroot
    tigervnc
    mesa
    mesa-utils
    vulkan-tools
    pipewire
    wireplumber
    pipewire-pulse
    curl
    wget
    zstd
    ttf-dejavu
)
pacman -S --needed --noconfirm "${packages[@]}"

echo "[4/5] Configuring the desktop account and locale..."
install -d -m 0700 -o alarm -g alarm /tmp/runtime-alarm
install -d -m 0755 -o alarm -g alarm \
    /home/alarm/Desktop \
    /home/alarm/Documents \
    /home/alarm/Downloads \
    /home/alarm/Music \
    /home/alarm/Pictures \
    /home/alarm/Videos \
    /home/alarm/Public

usermod -aG wheel,audio,video,render,input alarm
chmod 0440 /etc/sudoers.d/alarm

sed -i 's/^# *en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
grep -q '^en_US.UTF-8 UTF-8' /etc/locale.gen || echo 'en_US.UTF-8 UTF-8' >> /etc/locale.gen
locale-gen
chown -R alarm:alarm /home/alarm/.config /home/alarm/.local

echo "[5/5] Removing downloaded package archives..."
pacman -Scc --noconfirm

cat <<'EOF'

Desktop installation complete.
Enable either Termux:X11 desktop or AVNC desktop in Tiny Container Features,
then restart the container. CJK fonts and Box64/Steam remain optional.
EOF
