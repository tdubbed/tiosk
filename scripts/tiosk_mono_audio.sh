#!/bin/bash
# T-OSK mono audio setup.
# Creates a "mono" virtual sink that downmixes any stereo output to a single
# mono signal sent equally to both physical channels. Useful when the kiosk
# has a single speaker (or speakers placed so close that stereo separation
# is wasted) — otherwise half the audio gets lost to a missing right channel.
#
# Runs at login via autostart. Idempotent — if "mono" already exists it
# does nothing.

# Wait briefly for PipeWire to come up.
for i in $(seq 1 10); do
    if pactl info >/dev/null 2>&1; then break; fi
    sleep 1
done

# Find the real ALSA stereo sink (skip auto_null and our own mono sink).
MASTER=$(pactl list short sinks | awk '/alsa_output.*analog-stereo/ {print $2; exit}')
if [ -z "$MASTER" ]; then
    echo "No analog-stereo sink found; bailing." >&2
    exit 1
fi

# Idempotent: if mono sink already exists, just make sure it's default.
if pactl list short sinks | awk '{print $2}' | grep -qx mono; then
    pactl set-default-sink mono
    exit 0
fi

pactl load-module module-remap-sink \
    sink_name=mono \
    master="$MASTER" \
    channels=2 \
    channel_map=mono,mono >/dev/null

pactl set-default-sink mono
