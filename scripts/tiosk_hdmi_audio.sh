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

# Mirror the phantom HDMI display onto the real Elo so the screensaver
# doesn't span across a non-existent second monitor.
if command -v xrandr >/dev/null 2>&1; then
    if xrandr | grep -q "^HDMI1 connected"; then
        xrandr --output HDMI1 --auto --same-as DP2 2>/dev/null || true
    fi
fi
