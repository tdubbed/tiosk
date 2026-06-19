#!/usr/bin/env python3
"""TIOSK Launcher — space theme, rounded buttons, wallpaper."""
import tkinter as tk
from PIL import Image, ImageTk, ImageFilter
import subprocess, os

WALLPAPER = "/home/kiosk/wallpaper.jpg"

def pause_mopidy():
    subprocess.run(
        ["curl", "-s", "-m", "2", "-X", "POST",
         "-H", "Content-Type: application/json",
         "-d", '{"jsonrpc":"2.0","id":1,"method":"core.playback.pause"}',
         "http://localhost:6680/mopidy/rpc"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def launch_jukebox():
    root.lower()
    env = os.environ.copy()
    env["QT_IM_MODULE"] = "qtvirtualkeyboard"
    subprocess.run(["qiosk", "-f", "--profile-name", "kiosk",
                    "http://localhost:6680/iris/"], env=env)
    root.lift()
    root.attributes("-fullscreen", True)
    root.focus_force()

def launch_stream():
    pause_mopidy()
    root.lower()
    env = os.environ.copy()
    env["QT_IM_MODULE"] = "qtvirtualkeyboard"
    subprocess.run(["qiosk", "-f", "--profile-name", "stream",
                    "https://music.youtube.com/"], env=env)
    root.lift()
    root.attributes("-fullscreen", True)
    root.focus_force()

def launch_arcade():
    root.lower()
    try:
        subprocess.run(["retroarch", "--fullscreen"])
    except FileNotFoundError:
        pass
    root.lift()
    root.attributes("-fullscreen", True)
    root.focus_force()

def quit_launcher(event=None):
    root.destroy()

root = tk.Tk()
root.title("TIOSK")
root.attributes("-fullscreen", True)
root.configure(bg="#000000", cursor="none")
root.bind("<Escape>", quit_launcher)

SCREEN_W = root.winfo_screenwidth()
SCREEN_H = root.winfo_screenheight()

# Load + scale wallpaper. Slight darken for contrast.
img = Image.open(WALLPAPER)
# Fit cover: scale image to cover the screen, keeping aspect
img_w, img_h = img.size
scale = max(SCREEN_W / img_w, SCREEN_H / img_h)
new_size = (int(img_w * scale), int(img_h * scale))
img = img.resize(new_size, Image.LANCZOS)
# Crop center
left = (img.size[0] - SCREEN_W) // 2
top  = (img.size[1] - SCREEN_H) // 2
img = img.crop((left, top, left + SCREEN_W, top + SCREEN_H))
# Darken slightly for button contrast
dark = Image.new("RGB", img.size, "black")
img = Image.blend(img, dark, 0.35)
photo = ImageTk.PhotoImage(img)

# Canvas as full background
canvas = tk.Canvas(root, width=SCREEN_W, height=SCREEN_H,
                   highlightthickness=0, bg="#000000")
canvas.pack(fill="both", expand=True)
canvas.create_image(0, 0, anchor="nw", image=photo)

# Title — sci-fi vibe with soft glow effect
title_y = 130
canvas.create_text(SCREEN_W//2 + 2, title_y + 2, text="T  I  O  S  K",
                   font=("DejaVu Sans", 56, "bold"),
                   fill="#000000")  # shadow
canvas.create_text(SCREEN_W//2, title_y, text="T  I  O  S  K",
                   font=("DejaVu Sans", 56, "bold"),
                   fill="#a0d8ff")  # main

# Subtitle
canvas.create_text(SCREEN_W//2, title_y + 70,
                   text="— a self-contained signal —",
                   font=("DejaVu Sans", 14, "italic"),
                   fill="#7090b0")

# Buttons — rounded pills, centered, smaller
def make_pill(cx, cy, w, h, label, fill, accent, command):
    x1, y1, x2, y2 = cx - w//2, cy - h//2, cx + w//2, cy + h//2
    r = h // 2
    # Shadow
    canvas.create_oval(x1+4, y1+4, x1 + 2*r + 4, y2+4, fill="#000000", outline="")
    canvas.create_oval(x2 - 2*r + 4, y1+4, x2+4, y2+4, fill="#000000", outline="")
    canvas.create_rectangle(x1 + r + 4, y1+4, x2 - r + 4, y2+4, fill="#000000", outline="")
    # Main pill
    items = []
    items.append(canvas.create_oval(x1, y1, x1 + 2*r, y2, fill=fill, outline=accent, width=3))
    items.append(canvas.create_oval(x2 - 2*r, y1, x2, y2, fill=fill, outline=accent, width=3))
    items.append(canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=""))
    # Cover the lines from rectangle meeting circles
    items.append(canvas.create_line(x1 + r, y1, x2 - r, y1, fill=accent, width=3))
    items.append(canvas.create_line(x1 + r, y2, x2 - r, y2, fill=accent, width=3))
    # Label
    txt = canvas.create_text(cx, cy, text=label, font=("DejaVu Sans", 32, "bold"),
                              fill="#ffffff")
    items.append(txt)
    for item in items:
        canvas.tag_bind(item, "<Button-1>", lambda e: command())

btn_y = SCREEN_H // 2 + 80
btn_w, btn_h = 320, 110
spacing = 40
left_cx = SCREEN_W//2 - (btn_w + spacing)
mid_cx = SCREEN_W//2
right_cx = SCREEN_W//2 + (btn_w + spacing)

make_pill(left_cx, btn_y, btn_w, btn_h, "JUKEBOX",
          "#1e3a5f", "#5fa8ff", launch_jukebox)
make_pill(mid_cx, btn_y, btn_w, btn_h, "STREAM",
          "#1e5f3a", "#5fff9f", launch_stream)
make_pill(right_cx, btn_y, btn_w, btn_h, "ARCADE",
          "#5f1e3a", "#ff5fa8", launch_arcade)

root.mainloop()
