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
from PIL import Image, ImageTk
import subprocess, os

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


def launch_jukebox():
    global current_proc, current_mode
    if current_mode == "jukebox" and proc_alive():
        raise_app("qiosk")
        return
    kill_current()
    env = os.environ.copy()
    env["QT_IM_MODULE"] = "qtvirtualkeyboard"
    env["XCURSOR_THEME"] = "blank"
    env["XCURSOR_PATH"] = "/home/kiosk/.icons:/usr/share/icons"
    env["XCURSOR_SIZE"] = "1"
    root.lower()
    current_proc = subprocess.Popen(
        ["qiosk", "-f", "--profile-name", "kiosk",
         "http://localhost:6680/iris/"], env=env)
    current_mode = "jukebox"
    write_state("jukebox")


def launch_stream():
    global current_proc, current_mode
    if current_mode == "stream" and proc_alive():
        raise_app("qiosk")
        return
    kill_current()
    stop_mopidy()
    env = os.environ.copy()
    env["QT_IM_MODULE"] = "qtvirtualkeyboard"
    env["XCURSOR_THEME"] = "blank"
    env["XCURSOR_PATH"] = "/home/kiosk/.icons:/usr/share/icons"
    env["XCURSOR_SIZE"] = "1"
    root.lower()
    current_proc = subprocess.Popen(
        ["qiosk", "-f", "--profile-name", "stream",
         "https://music.youtube.com/"], env=env)
    current_mode = "stream"
    write_state("stream")


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
        root.attributes("-fullscreen", True)
    root.after(1000, check_child)


root = tk.Tk()
root.title("TIOSK")
root.attributes("-fullscreen", True)
root.configure(bg="#000000", cursor="none")
root.bind("<Escape>", quit_launcher)

SCREEN_W = root.winfo_screenwidth()
SCREEN_H = root.winfo_screenheight()

# Load + scale wallpaper. Slight darken for contrast.
img = Image.open(WALLPAPER)
img_w, img_h = img.size
scale = max(SCREEN_W / img_w, SCREEN_H / img_h)
new_size = (int(img_w * scale), int(img_h * scale))
img = img.resize(new_size, Image.LANCZOS)
left = (img.size[0] - SCREEN_W) // 2
top = (img.size[1] - SCREEN_H) // 2
img = img.crop((left, top, left + SCREEN_W, top + SCREEN_H))
dark = Image.new("RGB", img.size, "black")
img = Image.blend(img, dark, 0.35)
photo = ImageTk.PhotoImage(img)

canvas = tk.Canvas(root, width=SCREEN_W, height=SCREEN_H,
                   highlightthickness=0, bg="#000000")
canvas.pack(fill="both", expand=True)
canvas.create_image(0, 0, anchor="nw", image=photo)

title_y = 130
canvas.create_text(SCREEN_W // 2 + 2, title_y + 2, text="T  I  O  S  K",
                   font=("DejaVu Sans", 56, "bold"),
                   fill="#000000")
canvas.create_text(SCREEN_W // 2, title_y, text="T  I  O  S  K",
                   font=("DejaVu Sans", 56, "bold"),
                   fill="#a0d8ff")

canvas.create_text(SCREEN_W // 2, title_y + 70,
                   text="— a self-contained signal —",
                   font=("DejaVu Sans", 14, "italic"),
                   fill="#7090b0")


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
    txt = canvas.create_text(cx, cy, text=label, font=("DejaVu Sans", 32, "bold"),
                             fill="#ffffff")
    items.append(txt)
    for item in items:
        canvas.tag_bind(item, "<Button-1>", lambda e: command())


btn_y = SCREEN_H // 2 + 80
btn_w, btn_h = 320, 110
spacing = 40
left_cx = SCREEN_W // 2 - (btn_w + spacing)
mid_cx = SCREEN_W // 2
right_cx = SCREEN_W // 2 + (btn_w + spacing)

make_pill(left_cx, btn_y, btn_w, btn_h, "JUKEBOX",
          "#1e3a5f", "#5fa8ff", launch_jukebox)
make_pill(mid_cx, btn_y, btn_w, btn_h, "STREAM",
          "#1e5f3a", "#5fff9f", launch_stream)
make_pill(right_cx, btn_y, btn_w, btn_h, "ARCADE",
          "#5f1e3a", "#ff5fa8", launch_arcade)

check_child()
root.mainloop()
