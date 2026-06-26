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

# Re-exec after pulling so a self-modified deploy.sh takes effect this run.
# Bash holds the script open by inode; `git pull` writes a new inode and the
# old (in-memory) instructions would otherwise continue executing.
if [ -z "${TIOSK_DEPLOY_REEXEC:-}" ]; then
    echo "--- git pull ---"
    git pull --ff-only origin main
    export TIOSK_DEPLOY_REEXEC=1
    exec "$REPO_DIR/deploy.sh" "$@"
fi

echo "--- Ensure i3 + dex are installed ---"
if ! command -v i3 >/dev/null 2>&1 || ! command -v dex >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends i3 dex
fi

echo "--- Redeploy i3 config ---"
install -d -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    /home/"$KIOSK_USER"/.config/i3
install -m 644 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    config/i3/config /home/"$KIOSK_USER"/.config/i3/config

echo "--- Redeploy user scripts ---"
install -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    scripts/tiosk_launcher.py /home/"$KIOSK_USER"/tiosk_launcher.py
install -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    scripts/tiosk_volume_hud.py /home/"$KIOSK_USER"/tiosk_volume_hud.py
install -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    scripts/hide-cursor.sh /home/"$KIOSK_USER"/hide-cursor.sh
install -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    scripts/tiosk_dim_watcher.py /home/"$KIOSK_USER"/tiosk_dim_watcher.py
install -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    scripts/tiosk_eq.sh /home/"$KIOSK_USER"/tiosk_eq.sh
install -m 755 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    scripts/tiosk_hdmi_audio.sh /home/"$KIOSK_USER"/tiosk_hdmi_audio.sh
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

echo "--- Redeploy xscreensaver config ---"
install -m 644 -o "$KIOSK_USER" -g "$KIOSK_USER" \
    config/xscreensaver /home/"$KIOSK_USER"/.xscreensaver
# Hot-reload the running xscreensaver daemon (no-op if not running)
sudo -u "$KIOSK_USER" env DISPLAY=:0 XAUTHORITY=/home/"$KIOSK_USER"/.Xauthority \
    xscreensaver-command -restart >/dev/null 2>&1 || true

if [ "$RESTART_X" -eq 1 ]; then
    echo "--- Redeploy xorg + lightdm (requires X restart) ---"
    install -m 644 config/xorg-touch-calibration.conf \
        /etc/X11/xorg.conf.d/99-touch-calibration.conf
    install -m 644 config/xorg-tearfree.conf \
        /etc/X11/xorg.conf.d/20-tearfree.conf
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

# Re-launch as kiosk user attached to kiosk's display.
# Logs go under /home/kiosk/ (kiosk-owned dir) — /tmp's fs.protected_regular
# blocks even root from O_CREAT on a kiosk-owned file there.
LAUNCHER_LOG="/home/$KIOSK_USER/launcher.log"
HUD_LOG="/home/$KIOSK_USER/hud.log"
sudo -u "$KIOSK_USER" env DISPLAY=:0 XAUTHORITY=/home/"$KIOSK_USER"/.Xauthority \
    bash -c "setsid python3 /home/$KIOSK_USER/tiosk_launcher.py >> $LAUNCHER_LOG 2>&1 < /dev/null &"
sudo -u "$KIOSK_USER" env DISPLAY=:0 XAUTHORITY=/home/"$KIOSK_USER"/.Xauthority \
    bash -c "setsid python3 /home/$KIOSK_USER/tiosk_volume_hud.py >> $HUD_LOG 2>&1 < /dev/null &"

sleep 1
echo "Running processes:"
pgrep -af tiosk_ | head -4

# Restart Mopidy if its config changed (cheap to always do)
sudo -u "$KIOSK_USER" XDG_RUNTIME_DIR=/run/user/$(id -u "$KIOSK_USER") \
    systemctl --user restart mopidy.service || true

echo "=== Done ==="
