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

# EXTEND the desktop instead of mirror — Pioneer doesn't offer the Elo's
# 1280x1024 mode, so mirror would force a weird framebuffer size. Extended
# layout keeps DP2 as primary (full Elo resolution) with HDMI1 to the
# right as a dummy secondary that nobody sees. The launcher constrains
# itself to DP2 via explicit geometry (see tiosk_launcher.py).
if command -v xrandr >/dev/null 2>&1; then
    xrandr --output DP2 --primary --mode 1280x1024 --pos 0x0 2>/dev/null || true
    if xrandr | grep -q "^HDMI1 connected"; then
        xrandr --output HDMI1 --mode 1280x720 --right-of DP2 2>/dev/null || true
    fi
fi

# Paint the secondary (HDMI/Pioneer) area black so nothing leaks visually.
# xsetroot only handles the root window, which most desktops cover with a
# wallpaper — but xfdesktop respects xsetroot if no wallpaper is set.
xsetroot -solid black 2>/dev/null || true
