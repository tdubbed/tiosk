#!/bin/bash
# TIOSK deploy script.
# Pulls latest from GitHub, re-deploys files to live locations, restarts running processes.
#
# Usage: sudo tiosk-deploy [--restart-x]
#
#   Default: hot-redeploys launcher + HUD scripts and the wallpaper. Sends SIGTERM
#   to running launcher and HUD so the autostart re-spawns with the new code on
#   the next user-session re-entry. Currently we kill + relaunch as kiosk.
#
#   --restart-x: also reloads xorg.conf.d and lightdm config (forces full session
#   restart via X server termination). Use when calibration matrix or autologin
#   changed.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo."
    exit 1
fi

REPO_DIR="/opt/tiosk"
KIOSK_USER="kiosk"
RESTART_X=0

for arg in "$@"; do
    case "$arg" in
        --restart-x) RESTART_X=1 ;;
        *) echo "Unknown arg: $arg"; exit 1 ;;
    esac
done

echo "=== tiosk-deploy ==="
cd "$REPO_DIR"

echo "--- git pull ---"
git pull --ff-only origin main

echo "--- Redeploy user scripts ---"
install -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    scripts/tiosk_launcher.py /home/"$KIOSK_USER"/tiosk_launcher.py
install -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    scripts/tiosk_volume_hud.py /home/"$KIOSK_USER"/tiosk_volume_hud.py
install -m 755 scripts/calibrate-touch.sh /usr/local/bin/calibrate-touch.sh

if [ -f assets/wallpaper.jpg ]; then
    install -m 644 -o "$KIOSK_USER" -g "$KIOSK_USER" \
        assets/wallpaper.jpg /home/"$KIOSK_USER"/wallpaper.jpg
fi

echo "--- Redeploy autostart entries ---"
for f in autostart/*.desktop; do
    install -m 644 -o "$KIOSK_USER" -g "$KIOSK_USER" "$f" \
        "/home/$KIOSK_USER/.config/autostart/$(basename "$f")"
done

echo "--- Redeploy Mopidy config ---"
install -m 644 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    config/mopidy.conf /home/"$KIOSK_USER"/.config/mopidy/mopidy.conf

if [ "$RESTART_X" -eq 1 ]; then
    echo "--- Redeploy xorg + lightdm (requires X restart) ---"
    install -m 644 config/xorg-touch-calibration.conf \
        /etc/X11/xorg.conf.d/99-touch-calibration.conf
    install -m 644 config/lightdm-autologin.conf \
        /etc/lightdm/lightdm.conf.d/50-autologin.conf
    echo "Rebooting in 5 seconds..."
    sleep 5
    systemctl reboot -i
    exit 0
fi

echo "--- Restart kiosk launcher + HUD ---"
pkill -f tiosk_launcher 2>/dev/null || true
pkill -f tiosk_volume_hud 2>/dev/null || true
sleep 1

# Logs may be owned by a previous deployer; reset so kiosk can write them.
rm -f /tmp/launcher.log /tmp/hud.log
install -m 644 -o "$KIOSK_USER" -g "$KIOSK_USER" /dev/null /tmp/launcher.log
install -m 644 -o "$KIOSK_USER" -g "$KIOSK_USER" /dev/null /tmp/hud.log

# Re-launch as kiosk user attached to kiosk's display
sudo -u "$KIOSK_USER" env DISPLAY=:0 XAUTHORITY=/home/"$KIOSK_USER"/.Xauthority \
    setsid python3 /home/"$KIOSK_USER"/tiosk_launcher.py < /dev/null >> /tmp/launcher.log 2>&1 &
sudo -u "$KIOSK_USER" env DISPLAY=:0 XAUTHORITY=/home/"$KIOSK_USER"/.Xauthority \
    setsid python3 /home/"$KIOSK_USER"/tiosk_volume_hud.py < /dev/null >> /tmp/hud.log 2>&1 &

sleep 1
echo "Running processes:"
pgrep -af tiosk_ | head -4

# Restart Mopidy if its config changed (cheap to always do)
sudo -u "$KIOSK_USER" XDG_RUNTIME_DIR=/run/user/$(id -u "$KIOSK_USER") \
    systemctl --user restart mopidy.service || true

echo "=== Done ==="
