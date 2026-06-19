#!/bin/bash
# TIOSK bootstrap installer.
# Run as a sudoer on a fresh Xubuntu 26.04 install.
# Assumes SSH and the admin user are already set up.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo."
    exit 1
fi

KIOSK_USER="kiosk"
NAS_IP="192.168.68.100"
NAS_EXPORT="/mnt/storage/tdrive"
NAS_MOUNT="/mnt/nas"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== TIOSK installer ==="
echo "Repo: $REPO_DIR"

echo "--- Packages ---"
apt update
apt install -y \
    mopidy mopidy-local mopidy-mpd python3-pip \
    xdotool xinput xinput-calibrator wmctrl \
    retroarch libretro-* \
    nfs-common \
    beets python3-mutagen libchromaprint-tools python3-musicbrainzngs \
    python3-tk python3-pil python3-pil.imagetk \
    pulseaudio-utils pipewire-pulse pipewire-audio-client-libraries \
    xvkbd matchbox-keyboard \
    unclutter-xfixes \
    vim curl htop libxcb-cursor0

# Mopidy-Iris via pip (not in apt)
pip3 install --break-system-packages Mopidy-Iris

# Brave (fallback browser) — install only if missing
if ! command -v brave-browser >/dev/null 2>&1; then
    curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg \
        https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg arch=amd64] https://brave-browser-apt-release.s3.brave.com/ stable main" \
        > /etc/apt/sources.list.d/brave-browser-release.list
    apt update
    apt install -y brave-browser
fi

# Qiosk (primary browser) — install only if missing
if ! command -v qiosk >/dev/null 2>&1; then
    wget -qO- https://repository.salamek.cz/deb/salamek.gpg \
        | tee /usr/share/keyrings/salamek-archive-keyring.gpg > /dev/null
    echo "deb [signed-by=/usr/share/keyrings/salamek-archive-keyring.gpg] https://repository.salamek.cz/deb/pub all main" \
        > /etc/apt/sources.list.d/salamek.cz.list
    apt update
    apt install -y qiosk qt6-virtualkeyboard-plugin
fi

echo "--- NFS mount ---"
mkdir -p "$NAS_MOUNT"
if ! grep -q "$NAS_IP:$NAS_EXPORT" /etc/fstab; then
    echo "$NAS_IP:$NAS_EXPORT  $NAS_MOUNT  nfs  nofail,noatime,_netdev,x-systemd.automount,x-systemd.idle-timeout=600  0  0" \
        >> /etc/fstab
fi
systemctl daemon-reload
mount "$NAS_MOUNT" || true

echo "--- Kiosk user ---"
if ! id "$KIOSK_USER" &>/dev/null; then
    useradd -m -s /bin/bash -G audio,video,plugdev,input "$KIOSK_USER"
    echo "$KIOSK_USER:$KIOSK_USER" | chpasswd
fi
loginctl enable-linger "$KIOSK_USER"

echo "--- Deploy scripts ---"
install -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    "$REPO_DIR/scripts/tiosk_launcher.py" /home/"$KIOSK_USER"/tiosk_launcher.py
install -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    "$REPO_DIR/scripts/tiosk_volume_hud.py" /home/"$KIOSK_USER"/tiosk_volume_hud.py
install -m 755 "$REPO_DIR/scripts/calibrate-touch.sh" /usr/local/bin/calibrate-touch.sh

if [ -f "$REPO_DIR/assets/wallpaper.jpg" ]; then
    install -m 644 -o "$KIOSK_USER" -g "$KIOSK_USER" \
        "$REPO_DIR/assets/wallpaper.jpg" /home/"$KIOSK_USER"/wallpaper.jpg
fi

echo "--- XFCE autostart ---"
sudo -u "$KIOSK_USER" mkdir -p /home/"$KIOSK_USER"/.config/autostart \
    /home/"$KIOSK_USER"/.config/mopidy \
    /home/"$KIOSK_USER"/.config/systemd/user/default.target.wants
for f in "$REPO_DIR"/autostart/*.desktop; do
    install -m 644 -o "$KIOSK_USER" -g "$KIOSK_USER" "$f" \
        "/home/$KIOSK_USER/.config/autostart/$(basename "$f")"
done

echo "--- Mopidy ---"
install -m 644 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    "$REPO_DIR/config/mopidy.conf" /home/"$KIOSK_USER"/.config/mopidy/mopidy.conf
cat > /home/"$KIOSK_USER"/.config/systemd/user/mopidy.service << 'EOF'
[Unit]
Description=Mopidy music server
After=network.target sound.target

[Service]
ExecStart=/usr/bin/mopidy
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
chown "$KIOSK_USER":"$KIOSK_USER" /home/"$KIOSK_USER"/.config/systemd/user/mopidy.service
sudo -u "$KIOSK_USER" ln -sf /home/"$KIOSK_USER"/.config/systemd/user/mopidy.service \
    /home/"$KIOSK_USER"/.config/systemd/user/default.target.wants/mopidy.service

echo "--- Touch calibration ---"
install -m 644 "$REPO_DIR/config/xorg-touch-calibration.conf" \
    /etc/X11/xorg.conf.d/99-touch-calibration.conf

echo "--- LightDM auto-login ---"
mkdir -p /etc/lightdm/lightdm.conf.d
install -m 644 "$REPO_DIR/config/lightdm-autologin.conf" \
    /etc/lightdm/lightdm.conf.d/50-autologin.conf

echo "--- Suspend/sleep masked ---"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

echo "--- WoL on ethernet ---"
ETH=$(ip -brief link | awk '$1 ~ /^en/ {print $1; exit}')
if [ -n "$ETH" ]; then
    ethtool -s "$ETH" wol g || true
fi

echo "=== Done. Reboot for full effect. ==="
