#!/usr/bin/env python3
"""T-OSK dim watcher.

Sits on `xscreensaver-command -watch` and reacts to BLANK / UNBLANK events to
implement an iPhone-style dim-before-sleep AND re-activate the kiosk window
on wake so the on-screen keyboard keeps firing:

    0 min idle    →  normal brightness, no saver
   15 min idle    →  xscreensaver activates (BLANK event)  → start 15-min timer
   30 min idle    →  xrandr --brightness 0.35              ← this script
   90 min idle    →  DPMS turns the monitor off            (xscreensaver natively)
   touch/UNBLANK  →  restore brightness to 1.0             ← this script
                  →  xdotool windowactivate the kiosk app  ← this script

The wake-time windowactivate is what keeps Qt's virtual keyboard working after
a screensaver cycle. Without it, qiosk loses input focus and tapping a text
field does nothing.

Output is hard-coded to DP-2 (the AccuTouch's connector on the OptiPlex 5040).
If you ever change monitors/cables, update OUTPUT below.
"""
import subprocess
import threading
import time

OUTPUT = "DP-2"
DIM_DELAY_SEC = 15 * 60          # how long after BLANK before we dim
DIM_LEVEL = "0.35"               # xrandr --brightness arg when dimmed
FULL_LEVEL = "1.0"               # restored brightness
WAKE_REFOCUS_CLASSES = ("qiosk", "retroarch")
WAKE_REFOCUS_DELAY_SEC = 0.4     # let xscreensaver finish unmapping first


def set_brightness(level):
    subprocess.run(
        ["xrandr", "--output", OUTPUT, "--brightness", level],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


# Tracks the pending-dim timer so UNBLANK can cancel a dim that hasn't fired yet.
_dim_timer = None
_lock = threading.Lock()


def schedule_dim():
    global _dim_timer
    with _lock:
        if _dim_timer is not None:
            _dim_timer.cancel()
        _dim_timer = threading.Timer(DIM_DELAY_SEC, lambda: set_brightness(DIM_LEVEL))
        _dim_timer.daemon = True
        _dim_timer.start()


def reactivate_kiosk_window():
    """Refire xdotool windowactivate on whichever kiosk app is up.

    After a screensaver cycle, qiosk/retroarch lose the input focus that
    Qt's virtual keyboard hooks into. windowactivate --sync nudges it back
    without touching window geometry or restarting the app.
    """
    time.sleep(WAKE_REFOCUS_DELAY_SEC)
    for cls in WAKE_REFOCUS_CLASSES:
        try:
            out = subprocess.check_output(
                ["xdotool", "search", "--class", cls],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        if not out:
            continue
        wid = out.splitlines()[-1]  # most recently mapped match
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", wid],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return  # only refocus the first kiosk app we find


def cancel_dim_and_restore():
    global _dim_timer
    with _lock:
        if _dim_timer is not None:
            _dim_timer.cancel()
            _dim_timer = None
    set_brightness(FULL_LEVEL)
    threading.Thread(target=reactivate_kiosk_window, daemon=True).start()


def main():
    # Start at full brightness in case a previous run left it dimmed.
    set_brightness(FULL_LEVEL)

    while True:
        try:
            proc = subprocess.Popen(
                ["xscreensaver-command", "-watch"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1,
            )
            for line in proc.stdout:
                line = line.strip()
                if line.startswith("BLANK"):
                    schedule_dim()
                elif line.startswith("UNBLANK"):
                    cancel_dim_and_restore()
            proc.wait()
        except Exception:
            pass
        time.sleep(5)


if __name__ == "__main__":
    main()
