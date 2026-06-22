#!/bin/bash
# T-OSK HDMI audio setup.
# Switches PipeWire card profile to HDMI output and makes HDMI the default
# sink. Also mirrors the phantom HDMI "display" (Pioneer's EDID) onto DP2
# so the screensaver doesn't span across an invisible second monitor.
#
# Runs at login via autostart. Idempotent.

# Wait for PipeWire to come up.
for i in $(seq 1 15); do
    if pactl info >/dev/null 2>&1; then break; fi
    sleep 1
done

CARD="alsa_card.pci-0000_00_1f.3"
PROFILE="output:hdmi-stereo+input:analog-stereo"
SINK="alsa_output.pci-0000_00_1f.3.hdmi-stereo"

# Switch profile only if it's not already on HDMI
CURRENT=$(pactl list cards | awk '/Active Profile/ {print $3}')
if [ "$CURRENT" != "$PROFILE" ]; then
    pactl set-card-profile "$CARD" "$PROFILE" || true
fi

# Make HDMI the default sink
pactl set-default-sink "$SINK" 2>/dev/null || true

# Mirror Pioneer's HDMI to DP2 at HDMI's smallest matching mode (1280x720).
# Keeps the framebuffer at 1280x1024 and HDMI link electrically alive for
# audio.
if command -v xrandr >/dev/null 2>&1; then
    xrandr --output DP2 --primary --mode 1280x1024 --pos 0x0 2>/dev/null || true
    if xrandr | grep -q "^HDMI1 connected"; then
        xrandr --output HDMI1 --mode 1280x720 --same-as DP2 2>/dev/null || true
    fi

    # Tell the WM there is ONE logical monitor spanning the full Elo, not two.
    # Without this, XFWM treats DP2 and HDMI1 as separate monitors and
    # fullscreens apps onto the smaller one (HDMI's 1280x720).
    xrandr --setmonitor TIOSK 1280/340x1024/270+0+0 DP2 2>/dev/null || true
fi

# Kill XFCE panel — a kiosk should never show the taskbar.
pkill -x xfce4-panel 2>/dev/null || true
