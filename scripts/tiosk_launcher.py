#!/usr/bin/env python3
"""TIOSK Launcher — space theme, rounded buttons, wallpaper.

State model:
  current_proc / current_mode track the active app (qiosk-jukebox, qiosk-stream,
  retroarch). Buttons:
    * tapping the same mode that's already running → raise its window
    * tapping a different mode → kill the running one, start new
  HOME (on HUD) only lowers the active window; it does not kill the process,
  so YouTube Music audio (and ARCADE state) survives a trip to the launcher.
"""
import tkinter as tk
from PIL import Image, ImageTk, ImageEnhance
import subprocess, os, threading

WALLPAPER = "/home/kiosk/wallpaper.jpg"
STATE_FILE = "/tmp/tiosk_mode"

current_proc = None
current_mode = None


def write_state(mode):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(mode or "")
    except Exception:
        pass


def proc_alive():
    return current_proc is not None and current_proc.poll() is None


def kill_current():
    global current_proc, current_mode
    if proc_alive():
        try:
            current_proc.terminate()
            current_proc.wait(timeout=2)
        except Exception:
            try:
                current_proc.kill()
            except Exception:
                pass
    current_proc = None
    current_mode = None
    write_state("")


def raise_app(wm_class_substr):
    """Lower the launcher, raise the running app's window."""
    root.lower()
    subprocess.run(
        ["wmctrl", "-x", "-r", wm_class_substr, "-b", "remove,below"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(
        ["wmctrl", "-x", "-a", wm_class_substr],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop_mopidy():
    subprocess.run(
        ["curl", "-s", "-m", "2", "-X", "POST",
         "-H", "Content-Type: application/json",
         "-d", '{"jsonrpc":"2.0","id":1,"method":"core.playback.stop"}',
         "http://localhost:6680/mopidy/rpc"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def force_fullscreen(wm_class_substr):
    """Force the app's window borderless + 1280x1024 at 0,0.

    Verified live: setting _NET_WM_WINDOW_TYPE_SPLASH + unmap/remap +
    xdotool sync move/size gives zero frame extents and exact 1280x1024
    coverage. Other combinations (Motif borderless, fullscreen state,
    --setmonitor alone) failed because XFWM was still allocating 5px
    side + 29px title borders + offsetting the placement.
    """
    import time
    for attempt in range(8):
        time.sleep(0.5)
        try:
            out = subprocess.check_output(
                ["wmctrl", "-lx"], text=True, stderr=subprocess.DEVNULL)
        except Exception:
            continue
        wid = None
        for line in out.splitlines():
            parts = line.split(None, 4)
            if len(parts) >= 3 and wm_class_substr in parts[2].lower():
                wid = parts[0]
                break
        if not wid:
            continue
        # 1. Remove fullscreen / maximized states
        subprocess.run(
            ["wmctrl", "-i", "-r", wid, "-b",
             "remove,fullscreen,maximized_vert,maximized_horz"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 2. Set WINDOW_TYPE to SPLASH (XFWM renders no decorations)
        subprocess.run(
            ["xprop", "-id", wid, "-f", "_NET_WM_WINDOW_TYPE", "32a",
             "-set", "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_SPLASH"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 3. Unmap + remap so XFWM re-evaluates with new type
        subprocess.run(["xdotool", "windowunmap", "--sync", wid],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.3)
        subprocess.run(["xdotool", "windowmap", "--sync", wid],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.3)
        # 4. Exact position and size with --sync (waits for X to apply)
        subprocess.run(["xdotool", "windowmove", "--sync", wid, "0", "0"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["xdotool", "windowsize", "--sync", wid, "1280", "1024"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 5. Keep on top so it covers the launcher beneath
        subprocess.run(
            ["wmctrl", "-i", "-r", wid, "-b", "add,above"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 6. Force REAL input focus — SPLASH-type windows get
        # _NET_WM_STATE_FOCUSED but X11 input focus stays on Desktop, so
        # text fields don't receive input → virtual keyboard never triggers.
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", wid],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return


def launch_jukebox():
    global current_proc, current_mode
    if current_mode == "jukebox" and proc_alive():
        raise_app("qiosk")
        return
    kill_current()
    env = os.environ.copy()
    env["QT_IM_MODULE"] = "qtvirtualkeyboard"
    # Force the IM context to load eagerly. Without this, QtWebEngine
    # sometimes fails to register IM focus events from Chromium-rendered
    # text fields, so tapping a text field never triggers the keyboard.
    env["QT_VIRTUALKEYBOARD_DESKTOP_DISABLE"] = "0"
    env["QT_VIRTUALKEYBOARD_HIDE_ON_NO_FOCUS"] = "0"
    env["XCURSOR_THEME"] = "blank"
    env["XCURSOR_PATH"] = "/home/kiosk/.icons:/usr/share/icons"
    env["XCURSOR_SIZE"] = "1"
    root.lower()
    current_proc = subprocess.Popen(
        ["qiosk", "-f", "--profile-name", "kiosk",
         "http://localhost:6680/iris/"], env=env)
    current_mode = "jukebox"
    write_state("jukebox")
    threading.Thread(target=force_fullscreen, args=("qiosk",), daemon=True).start()


def launch_stream():
    global current_proc, current_mode
    if current_mode == "stream" and proc_alive():
        raise_app("qiosk")
        return
    kill_current()
    stop_mopidy()
    env = os.environ.copy()
    env["QT_IM_MODULE"] = "qtvirtualkeyboard"
    # Force the IM context to load eagerly. Without this, QtWebEngine
    # sometimes fails to register IM focus events from Chromium-rendered
    # text fields, so tapping a text field never triggers the keyboard.
    env["QT_VIRTUALKEYBOARD_DESKTOP_DISABLE"] = "0"
    env["QT_VIRTUALKEYBOARD_HIDE_ON_NO_FOCUS"] = "0"
    env["XCURSOR_THEME"] = "blank"
    env["XCURSOR_PATH"] = "/home/kiosk/.icons:/usr/share/icons"
    env["XCURSOR_SIZE"] = "1"
    root.lower()
    current_proc = subprocess.Popen(
        ["qiosk", "-f", "--profile-name", "stream",
         "https://music.youtube.com/"], env=env)
    current_mode = "stream"
    write_state("stream")
    threading.Thread(target=force_fullscreen, args=("qiosk",), daemon=True).start()


def launch_arcade():
    global current_proc, current_mode
    if current_mode == "arcade" and proc_alive():
        raise_app("retroarch")
        return
    kill_current()
    stop_mopidy()
    root.lower()
    try:
        current_proc = subprocess.Popen(["retroarch", "--fullscreen"])
        current_mode = "arcade"
        write_state("arcade")
        threading.Thread(target=force_fullscreen, args=("retroarch",), daemon=True).start()
    except FileNotFoundError:
        pass


def quit_launcher(event=None):
    kill_current()
    root.destroy()


def check_child():
    """If the active child died on its own, return to launcher view."""
    global current_proc, current_mode
    if current_mode and not proc_alive():
        current_proc = None
        current_mode = None
        write_state("")
        root.lift()
        root.geometry(f"{SCREEN_W}x{SCREEN_H}+0+0")
    root.after(1000, check_child)


root = tk.Tk()
root.title("TIOSK")
root.configure(bg="#000000", cursor="none")
root.bind("<Escape>", quit_launcher)

# Use explicit framebuffer-spanning geometry instead of -fullscreen.
# Reason: -fullscreen is MONITOR-relative on X11. With HDMI mirror enabled
# (HDMI1 at 1280x720 mirroring DP2 at 1280x1024), XFWM treats them as two
# monitors and fullscreens onto the SMALLER one — leaving a 304px strip
# of XFCE wallpaper visible at the bottom of the Elo. overrideredirect +
# explicit geometry covers the full framebuffer regardless.
SCREEN_W = root.winfo_screenwidth()
SCREEN_H = root.winfo_screenheight()
root.overrideredirect(True)
root.geometry(f"{SCREEN_W}x{SCREEN_H}+0+0")

# Load + scale wallpaper. Keep contrast high — old code dimmed it to 65% to
# make pills readable, but that killed the "crisp" feel. With darker pills
# (more solid fill + outline), we can leave the wallpaper at full punch.
img = Image.open(WALLPAPER)
img_w, img_h = img.size
scale = max(SCREEN_W / img_w, SCREEN_H / img_h)
new_size = (int(img_w * scale), int(img_h * scale))
img = img.resize(new_size, Image.LANCZOS)
left = (img.size[0] - SCREEN_W) // 2
top = (img.size[1] - SCREEN_H) // 2
img = img.crop((left, top, left + SCREEN_W, top + SCREEN_H))
# Minimal darken (just enough so title text reads) + slight contrast boost
dark = Image.new("RGB", img.size, "black")
img = Image.blend(img, dark, 0.15)
img = ImageEnhance.Contrast(img).enhance(1.10)
img = ImageEnhance.Color(img).enhance(1.15)
photo = ImageTk.PhotoImage(img)

canvas = tk.Canvas(root, width=SCREEN_W, height=SCREEN_H,
                   highlightthickness=0, bg="#000000")
canvas.pack(fill="both", expand=True)
canvas.create_image(0, 0, anchor="nw", image=photo)

title_y = 130
canvas.create_text(SCREEN_W // 2 + 2, title_y + 2, text="T-OSK",
                   font=("DejaVu Sans", 56, "bold"),
                   fill="#000000")
canvas.create_text(SCREEN_W // 2, title_y, text="T-OSK",
                   font=("DejaVu Sans", 56, "bold"),
                   fill="#a0d8ff")


def make_pill(cx, cy, w, h, label, fill, accent, command):
    x1, y1, x2, y2 = cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2
    r = h // 2
    canvas.create_oval(x1 + 4, y1 + 4, x1 + 2 * r + 4, y2 + 4, fill="#000000", outline="")
    canvas.create_oval(x2 - 2 * r + 4, y1 + 4, x2 + 4, y2 + 4, fill="#000000", outline="")
    canvas.create_rectangle(x1 + r + 4, y1 + 4, x2 - r + 4, y2 + 4, fill="#000000", outline="")
    items = []
    items.append(canvas.create_oval(x1, y1, x1 + 2 * r, y2, fill=fill, outline=accent, width=3))
    items.append(canvas.create_oval(x2 - 2 * r, y1, x2, y2, fill=fill, outline=accent, width=3))
    items.append(canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=""))
    items.append(canvas.create_line(x1 + r, y1, x2 - r, y1, fill=accent, width=3))
    items.append(canvas.create_line(x1 + r, y2, x2 - r, y2, fill=accent, width=3))
    txt = canvas.create_text(cx, cy, text=label, font=("DejaVu Sans", 42, "bold"),
                             fill="#ffffff")
    items.append(txt)
    for item in items:
        canvas.tag_bind(item, "<Button-1>", lambda e: command())


btn_y = SCREEN_H // 2 + 80
btn_w, btn_h = 400, 140
spacing = 80
left_cx = SCREEN_W // 2 - (btn_w + spacing) // 2
right_cx = SCREEN_W // 2 + (btn_w + spacing) // 2

make_pill(left_cx, btn_y, btn_w, btn_h, "STREAM",
          "#1e5f3a", "#5fff9f", launch_stream)
make_pill(right_cx, btn_y, btn_w, btn_h, "ARCADE",
          "#5f1e3a", "#ff5fa8", launch_arcade)

check_child()
root.mainloop()
