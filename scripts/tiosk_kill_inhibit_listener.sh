#!/bin/bash
# Kill xscreensaver-systemd so the saver fires on its idle timer regardless
# of browser/media inhibits. We want the saver to come up even when music
# is playing — without this, YouTube Music holds an inhibit indefinitely
# and the screen never blanks.
#
# RetroArch doesn't send screensaver inhibits, so ARCADE is unaffected.
# Runs at login. Belt-and-suspenders: also kills on a 30s loop in case the
# parent xscreensaver process respawns it.

while true; do
    pkill -x xscreensaver-systemd 2>/dev/null
    sleep 30
done
