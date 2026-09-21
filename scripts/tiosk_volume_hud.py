#!/usr/bin/env python3
"""TIOSK HUD — collapsible. One tiny button until tapped, then full panel.

Expanded panel layout (top → bottom):
   ×       (close)
   75%     (prominent percentage — top of panel, big)
   +       (volume up)
   M       (mute toggle)
   -       (volume down)
   EQ      (opens equalizer window)
   ☀       (screen brightness — opens a level picker)
   🏠      (home — sends current app behind launcher)
"""
import tkinter as tk
import subprocess, os, re, pathlib, time

os.environ["XDG_RUNTIME_DIR"] = "/run/user/1001"

EQ_SCRIPT = "/home/kiosk/tiosk_eq.sh"

# Screen brightness. xrandr's --brightness is a gamma multiplier on the
# output, not a backlight — but it is what the dim watcher already uses on
# this monitor, so there is exactly one mechanism.
#
# ★ The chosen level has to be SHARED with tiosk_dim_watcher.py. That script
# restores brightness on every UNBLANK, and it used to restore a hard-coded
# 1.0 — so a level set here would survive only until the next screensaver
# cycle, then silently snap back to blinding. Both scripts now read this file.
BRIGHTNESS_FILE = "/home/kiosk/.tiosk_brightness"
BRIGHTNESS_FALLBACK_OUTPUT = "DP2"  # only if detection finds nothing
BRIGHTNESS_LEVELS = [("FULL", 1.0), ("DIM", 0.7), ("DARK", 0.45), ("NIGHT", 0.25)]
AUTO_COLLAPSE_SEC = 20  # seconds of inactivity before HUD auto-collapses

# Last time the user interacted with the expanded HUD. expand() and every
# button callback bump this so the auto-collapse timer resets on touch.
last_activity = 0


def get_volume():
    try:
        out = subprocess.check_output(
            ["pactl", "get-sink-volume", "@DEFAULT_SINK@"], text=True)
        m = re.search(r"/\s*(\d+)%", out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return 0


def get_mute():
    try:
        out = subprocess.check_output(
            ["pactl", "get-sink-mute", "@DEFAULT_SINK@"], text=True)
        return "yes" in out
    except Exception:
        return False


def bump_activity():
    global last_activity
    last_activity = time.time()


def set_vol(delta):
    bump_activity()
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@",
                    f"{'+' if delta >= 0 else ''}{delta}%"])
    update_pct()


def toggle_mute():
    bump_activity()
    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
    update_pct()


def go_home():
    bump_activity()
    # i3: just switch to workspace 1 (the launcher's workspace). Apps in
    # other workspaces stay running, audio keeps playing, video resumes.
    subprocess.run(["i3-msg", "workspace", "number", "1"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    collapse()


def detect_output():
    """Ask X which output to dim, instead of trusting a hard-coded name.

    ★ This was `DP-2` for a long time and the real name is `DP2` — xrandr
    answered "warning: output DP-2 not found; ignoring" into a DEVNULL'd
    stderr, so the dim never happened and nothing ever said so. Detecting it
    means a swapped cable or a new monitor cannot silently kill this again.
    Prefers the primary; HDMI1 (the TV) is deliberately not the fallback.
    """
    try:
        out = subprocess.check_output(["xrandr", "-q"], text=True,
                                      stderr=subprocess.DEVNULL)
    except Exception:
        return BRIGHTNESS_FALLBACK_OUTPUT
    connected = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "connected":
            connected.append(parts[0])
            if "primary" in parts[:3]:
                return parts[0]
    for name in connected:
        if name.startswith("DP"):
            return name
    return connected[0] if connected else BRIGHTNESS_FALLBACK_OUTPUT


def read_brightness():
    try:
        with open(BRIGHTNESS_FILE) as f:
            v = float(f.read().strip())
        return v if 0.1 <= v <= 1.0 else 1.0
    except Exception:
        return 1.0


def set_brightness(level):
    """Apply a level and remember it. Written before it is applied so the dim
    watcher can never restore a stale value if the two race."""
    bump_activity()
    level = max(0.1, min(1.0, float(level)))
    try:
        with open(BRIGHTNESS_FILE, "w") as f:
            f.write("{:.2f}".format(level))
    except OSError:
        pass
    subprocess.run(["xrandr", "--output", detect_output(),
                    "--brightness", "{:.2f}".format(level)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if hasattr(open_brightness, "_win") and open_brightness._win.winfo_exists():
        open_brightness._win.destroy()
    scr_status.config(text="SCREEN: {}%".format(int(round(level * 100))))


def open_brightness():
    """Level picker, same shape as the EQ window."""
    bump_activity()
    if hasattr(open_brightness, "_win") and open_brightness._win.winfo_exists():
        open_brightness._win.lift()
        return
    win = tk.Toplevel(root)
    open_brightness._win = win
    win.title("Screen")
    win.overrideredirect(True)
    win.configure(bg="#000000", cursor="none")
    W, H = 260, 400
    win.geometry(f"{W}x{H}+{X + W_EXPANDED + 10}+{Y_EXPANDED}")

    tk.Label(win, text="SCREEN", bg="#000000", fg="#ffd08a",
             font=("DejaVu Sans", 18, "bold")).pack(pady=(10, 6))

    cur = read_brightness()
    for name, lvl in BRIGHTNESS_LEVELS:
        on = abs(cur - lvl) < 0.03
        tk.Button(win, text=f"{name}  {int(lvl*100)}%",
                  font=("DejaVu Sans", 18, "bold"),
                  bg="#6e5e2e" if on else "#2a2a2a", fg="#ffffff",
                  activebackground="#8e7e4e", bd=0, height=2,
                  command=lambda l=lvl: set_brightness(l)).pack(padx=10, pady=5, fill="x")

    tk.Button(win, text="× CLOSE", font=("DejaVu Sans", 14, "bold"),
              bg="#444444", fg="#ffffff", activebackground="#666666",
              bd=0, height=1, command=win.destroy).pack(padx=10, pady=(12, 8), fill="x")


def apply_eq(preset):
    """Apply named EQ preset by invoking the helper script."""
    bump_activity()
    subprocess.run([EQ_SCRIPT, preset],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    eq_status.config(text=f"EQ: {preset.upper()}")


def fire_saver():
    """Manually trigger the screensaver right now."""
    # Don't bump activity — we WANT the HUD to collapse after this fires
    subprocess.run(
        ["xscreensaver-command", "-activate"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    collapse()


def open_eq():
    """Modal-ish toplevel with three preset buttons."""
    if hasattr(open_eq, "_win") and open_eq._win.winfo_exists():
        open_eq._win.lift()
        return
    win = tk.Toplevel(root)
    open_eq._win = win
    win.title("EQ")
    win.overrideredirect(True)
    win.configure(bg="#000000", cursor="none")
    W, H = 260, 360
    x = X + W_EXPANDED + 10
    y = Y_EXPANDED
    win.geometry(f"{W}x{H}+{x}+{y}")

    def pick(p):
        apply_eq(p)

    tk.Label(win, text="EQ", bg="#000000", fg="#a0d8ff",
             font=("DejaVu Sans", 18, "bold")).pack(pady=(10, 6))

    btn_font = ("DejaVu Sans", 18, "bold")
    tk.Button(win, text="FLAT", font=btn_font,
              bg="#2a2a2a", fg="#ffffff", activebackground="#444444",
              bd=0, height=2,
              command=lambda: pick("flat")).pack(padx=10, pady=6, fill="x")
    tk.Button(win, text="BASS BOOST", font=btn_font,
              bg="#1e3a5f", fg="#ffffff", activebackground="#2e5e9f",
              bd=0, height=2,
              command=lambda: pick("bass")).pack(padx=10, pady=6, fill="x")
    tk.Button(win, text="VOCAL", font=btn_font,
              bg="#5f1e3a", fg="#ffffff", activebackground="#9f2e5e",
              bd=0, height=2,
              command=lambda: pick("vocal")).pack(padx=10, pady=6, fill="x")
    tk.Button(win, text="× CLOSE", font=("DejaVu Sans", 14, "bold"),
              bg="#444444", fg="#ffffff", activebackground="#666666",
              bd=0, height=1,
              command=win.destroy).pack(padx=10, pady=(14, 8), fill="x")


def update_pct():
    v = get_volume()
    pct_label.config(text="MUTE" if get_mute() else f"{v}%")


# ---- Window setup ----
root = tk.Tk()
root.title("Vol")
root.overrideredirect(True)
root.configure(bg="#000000", cursor="none")

SCREEN_W = root.winfo_screenwidth()
SCREEN_H = root.winfo_screenheight()
W_COLLAPSED = 60
H_COLLAPSED = 60
W_EXPANDED = 130
H_EXPANDED = 570
X = 5
Y_COLLAPSED = 735
Y_EXPANDED = 735 - H_EXPANDED + H_COLLAPSED

collapsed_frame = tk.Frame(root, bg="#000000")
expanded_frame = tk.Frame(root, bg="#000000")


def expand():
    bump_activity()
    root.geometry(f"{W_EXPANDED}x{H_EXPANDED}+{X}+{Y_EXPANDED}")
    collapsed_frame.pack_forget()
    expanded_frame.pack(fill="both", expand=True)
    update_pct()


def collapse():
    root.geometry(f"{W_COLLAPSED}x{H_COLLAPSED}+{X}+{Y_COLLAPSED}")
    expanded_frame.pack_forget()
    collapsed_frame.pack(fill="both", expand=True)


# ---- Collapsed: single button ----
tk.Button(collapsed_frame, text="≡", font=("DejaVu Sans", 32, "bold"),
          bg="#222222", fg="#ffffff", activebackground="#444444",
          bd=0, command=expand).pack(fill="both", expand=True, padx=2, pady=2)

# ---- Expanded: prominent % at top, then controls ----
btn_font = ("DejaVu Sans", 22, "bold")

tk.Button(expanded_frame, text="×", font=("DejaVu Sans", 16, "bold"),
          bg="#444444", fg="#ffffff", activebackground="#666666",
          bd=0, height=1, command=collapse).pack(pady=(2, 4), padx=6, fill="x")

# BIG percentage display at top
pct_label = tk.Label(expanded_frame, text="--%",
                     font=("DejaVu Sans", 30, "bold"),
                     bg="#0a0a0a", fg="#5fff9f",
                     pady=8)
pct_label.pack(pady=(0, 6), padx=6, fill="x")

tk.Button(expanded_frame, text="+", font=btn_font, bg="#1e3a5f", fg="#ffffff",
          activebackground="#2e5e9f", bd=0, height=1,
          command=lambda: set_vol(5)).pack(pady=2, padx=6, fill="x")
tk.Button(expanded_frame, text="M", font=btn_font, bg="#3a3a3a", fg="#ffffff",
          activebackground="#5a5a5a", bd=0, height=1,
          command=toggle_mute).pack(pady=2, padx=6, fill="x")
tk.Button(expanded_frame, text="-", font=btn_font, bg="#5f1e3a", fg="#ffffff",
          activebackground="#9f2e5e", bd=0, height=1,
          command=lambda: set_vol(-5)).pack(pady=2, padx=6, fill="x")
tk.Button(expanded_frame, text="EQ", font=("DejaVu Sans", 18, "bold"),
          bg="#3a5f1e", fg="#ffffff", activebackground="#5e9f2e",
          bd=0, height=1, command=open_eq).pack(pady=2, padx=6, fill="x")
tk.Button(expanded_frame, text="☾", font=("DejaVu Sans", 24, "bold"),
          bg="#1e2a5f", fg="#a0d8ff", activebackground="#2e3a8f",
          bd=0, height=1, command=fire_saver).pack(pady=2, padx=6, fill="x")
tk.Button(expanded_frame, text="☀", font=("DejaVu Sans", 22, "bold"),
          bg="#6e5e2e", fg="#ffffff", activebackground="#8e7e4e",
          bd=0, height=1, command=open_brightness).pack(pady=2, padx=6, fill="x")
tk.Button(expanded_frame, text="🏠", font=("DejaVu Sans", 22, "bold"),
          bg="#6e5e2e", fg="#ffffff", activebackground="#8e7e4e",
          bd=0, height=1, command=go_home).pack(pady=2, padx=6, fill="x")

# Tiny current EQ status indicator at bottom
eq_status = tk.Label(expanded_frame, text="",
                     font=("DejaVu Sans", 10),
                     bg="#000000", fg="#7090b0")
eq_status.pack(pady=2)

scr_status = tk.Label(expanded_frame, text="",
                      font=("DejaVu Sans", 10),
                      bg="#000000", fg="#b09070")
scr_status.pack(pady=(0, 2))

# Re-apply the saved level on launch — xrandr brightness resets to 1.0 on
# every X start, so without this a dimmed kiosk comes back blinding.
_saved = read_brightness()
if _saved < 1.0:
    set_brightness(_saved)
else:
    scr_status.config(text="SCREEN: 100%")

# Start collapsed
collapse()


def refresh():
    if expanded_frame.winfo_ismapped():
        update_pct()
        # Auto-collapse after inactivity
        if time.time() - last_activity > AUTO_COLLAPSE_SEC:
            collapse()
    root.after(1000, refresh)


refresh()
root.mainloop()
