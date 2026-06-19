#!/usr/bin/env python3
"""TIOSK HUD — collapsible. One tiny button until tapped, then full panel."""
import tkinter as tk
import subprocess, os, re

os.environ["XDG_RUNTIME_DIR"] = "/run/user/1001"

def get_volume():
    try:
        out = subprocess.check_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], text=True)
        m = re.search(r"/\s*(\d+)%", out)
        if m: return int(m.group(1))
    except: pass
    return 0

def get_mute():
    try:
        out = subprocess.check_output(["pactl", "get-sink-mute", "@DEFAULT_SINK@"], text=True)
        return "yes" in out
    except: return False

def set_vol(delta):
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@",
                    f"{'+' if delta>=0 else ''}{delta}%"])
    update_label()

def toggle_mute():
    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
    update_label()

def go_home():
    # Don't kill — just send the foreground app behind the launcher so audio
    # (YouTube Music in Stream) keeps playing. Launcher resumes or replaces
    # the running app when a mode button is tapped.
    for cls in ["qiosk", "retroarch"]:
        subprocess.run(["wmctrl", "-x", "-r", cls, "-b", "add,below"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["wmctrl", "-a", "TIOSK"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    collapse()

def update_label():
    v = get_volume()
    label.config(text="MUTE" if get_mute() else f"{v}%")

# ---- Window setup ----
root = tk.Tk()
root.title("Vol")
root.overrideredirect(True)
root.configure(bg="#000000", cursor="none")

SCREEN_W = root.winfo_screenwidth()
SCREEN_H = root.winfo_screenheight()
W_COLLAPSED = 60
H_COLLAPSED = 60
W_EXPANDED = 110
H_EXPANDED = 360
X = 5
Y_COLLAPSED = 735
Y_EXPANDED = 735 - H_EXPANDED + H_COLLAPSED

# ---- Two frames: collapsed and expanded ----
collapsed_frame = tk.Frame(root, bg="#000000")
expanded_frame = tk.Frame(root, bg="#000000")

def expand():
    root.geometry(f"{W_EXPANDED}x{H_EXPANDED}+{X}+{Y_EXPANDED}")
    collapsed_frame.pack_forget()
    expanded_frame.pack(fill="both", expand=True)
    update_label()
    update_label()

def collapse():
    root.geometry(f"{W_COLLAPSED}x{H_COLLAPSED}+{X}+{Y_COLLAPSED}")
    expanded_frame.pack_forget()
    collapsed_frame.pack(fill="both", expand=True)

# ---- Collapsed: single button ----
tk.Button(collapsed_frame, text="≡", font=("DejaVu Sans", 32, "bold"),
          bg="#222222", fg="#ffffff", activebackground="#444444",
          bd=0, command=expand).pack(fill="both", expand=True, padx=2, pady=2)

# ---- Expanded: full controls + close ----
btn_font = ("DejaVu Sans", 22, "bold")
tk.Button(expanded_frame, text="×", font=("DejaVu Sans", 18, "bold"),
          bg="#444444", fg="#ffffff", activebackground="#666666",
          bd=0, height=1, command=collapse).pack(pady=(2, 2), padx=6, fill="x")
tk.Button(expanded_frame, text="+", font=btn_font, bg="#1e3a5f", fg="#ffffff",
          activebackground="#2e5e9f", bd=0, height=2,
          command=lambda: set_vol(5)).pack(pady=2, padx=6, fill="x")
tk.Button(expanded_frame, text="M", font=btn_font, bg="#3a3a3a", fg="#ffffff",
          activebackground="#5a5a5a", bd=0, height=2,
          command=toggle_mute).pack(pady=2, padx=6, fill="x")
tk.Button(expanded_frame, text="-", font=btn_font, bg="#5f1e3a", fg="#ffffff",
          activebackground="#9f2e5e", bd=0, height=2,
          command=lambda: set_vol(-5)).pack(pady=2, padx=6, fill="x")
tk.Button(expanded_frame, text="🏠", font=("DejaVu Sans", 22, "bold"),
          bg="#6e5e2e", fg="#ffffff", activebackground="#8e7e4e",
          bd=0, height=2, command=go_home).pack(pady=2, padx=6, fill="x")
label = tk.Label(expanded_frame, text="", font=("DejaVu Sans", 13, "bold"),
                 bg="#000000", fg="#ffffff")
label.pack(pady=4)

# Start collapsed
collapse()

def refresh():
    if expanded_frame.winfo_ismapped():
        update_label()
    root.after(2000, refresh)
refresh()

root.mainloop()
