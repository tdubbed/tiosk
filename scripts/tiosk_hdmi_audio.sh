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
# This keeps the framebuffer at 1280x1024 (the Elo's native — max of both
# dimensions), so the launcher renders correctly, touch calibration stays
# valid, and nothing about the input pipeline changes. Pioneer shows the
# upper-left 1280x720 of the Elo desktop (nobody sees it). Crucially,
# HDMI1 stays *electrically connected* with a real mode → HDMI audio link
# stays alive.
if command -v xrandr >/dev/null 2>&1; then
    xrandr --output DP2 --primary --mode 1280x1024 --pos 0x0 2>/dev/null || true
    if xrandr | grep -q "^HDMI1 connected"; then
        xrandr --output HDMI1 --mode 1280x720 --same-as DP2 2>/dev/null || true
    fi
fi
