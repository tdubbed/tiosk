#!/usr/bin/env python3
"""TIOSK Launcher running under i3.

i3 workspaces map to kiosk app slots:
  1 = launcher (this tk window)
  2 = STREAM    (chromium-stream)
  3 = ARCADE    (retroarch)
  4 = SERVICES  (chromium-service)

Switching apps = `i3-msg workspace N`. Launch happens by spawning
chromium/retroarch with the right WM_CLASS, which i3's `assign` rules
route to the correct workspace automatically. Multiple kiosk apps
coexist (each in its own workspace), so STREAM keeps playing audio
in the background while you're using SERVICES.
"""
import tkinter as tk
from PIL import Image, ImageTk, ImageEnhance
import subprocess, os

WALLPAPER = "/home/kiosk/wallpaper.jpg"
STATE_FILE = "/tmp/tiosk_mode"

STREAM_ITEMS = [
    ("YouTube Music", "https://music.youtube.com/", "stream:ytmusic", "stream-ytmusic"),
    ("YouTube",       "https://www.youtube.com/",   "stream:youtube", "stream-youtube"),
]

SERVICE_ITEMS = [
    ("Tymo",            "https://tymo.westonfamily.lol/",   "service:tymo",    "svc-tymo"),
    ("AnyList",         "https://www.anylist.com/web",      "service:anylist", "svc-anylist"),
    ("Ultimate Guitar", "https://www.ultimate-guitar.com/", "service:ug",      "svc-ug"),
]

# WM_CLASS values — must match i3 config's `assign` rules.
STREAM_CLASS = "chromium-stream"
SERVICE_CLASS = "chromium-service"

# Per-class tracking. One chromium per class.
procs = {}          # wm_class -> Popen
current_urls = {}   # wm_class -> currently-loaded URL
_picker_window = None


def write_state(mode):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(mode or "")
    except Exception:
        pass


def i3msg(*args):
    subprocess.run(["i3-msg"] + list(args),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def alive(wm_class):
    p = procs.get(wm_class)
    return p is not None and p.poll() is None


def kill_proc(wm_class):
    p = procs.pop(wm_class, None)
    current_urls.pop(wm_class, None)
    if p is None:
        return
    try:
        p.terminate()
        p.wait(timeout=2)
    except Exception:
        try: p.kill()
        except Exception: pass


def cleanup_dead():
    for cls in list(procs):
        if procs[cls].poll() is not None:
            procs.pop(cls, None)
            current_urls.pop(cls, None)


class _AdoptedProc:
    """Stand-in for subprocess.Popen when we adopt a process that was
    started by a previous launcher instance. Exposes the .poll() /
    .terminate() / .kill() / .wait() surface the rest of the launcher
    uses, backed by os.kill(pid, 0) for liveness."""
    def __init__(self, pid):
        self.pid = pid
    def poll(self):
        try:
            os.kill(self.pid, 0)
            return None
        except OSError:
            return -1
    def terminate(self):
        try: os.kill(self.pid, 15)
        except OSError: pass
    def kill(self):
        try: os.kill(self.pid, 9)
        except OSError: pass
    def wait(self, timeout=None):
        import time
        deadline = time.time() + (timeout if timeout is not None else 2)
        while time.time() < deadline:
            if self.poll() is not None:
                return
            time.sleep(0.1)


def adopt_orphans_at_startup():
    """The launcher process is restarted by tiosk-deploy --dev, but its
    child chromium/retroarch processes survive. Find them by class /
    name, parse their --app=URL out of /proc/PID/cmdline, and register
    them in procs/current_urls so tapping the same option again raises
    the existing window instead of spawning a duplicate.

    Skips chromium subprocesses (renderer/zygote/utility/gpu) — they have
    --type= in their cmdline; we only want the main browser process."""
    import re
    for wm_class in [STREAM_CLASS, SERVICE_CLASS]:
        try:
            out = subprocess.check_output(
                ["pgrep", "-f", f"--class={wm_class}"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
        except subprocess.CalledProcessError:
            continue
        for pid_str in out.splitlines():
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().replace(b"\0", b" ").decode("utf-8", "ignore")
            except OSError:
                continue
            if "--type=" in cmdline:
                continue
            m = re.search(r"--app=(\S+)", cmdline)
            if not m:
                continue
            procs[wm_class] = _AdoptedProc(pid)
            current_urls[wm_class] = m.group(1)
            break
    try:
        out = subprocess.check_output(
            ["pgrep", "-x", "retroarch"], text=True, stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            procs["retroarch"] = _AdoptedProc(int(out.splitlines()[0]))
    except subprocess.CalledProcessError:
        pass


def _chromium_env():
    env = os.environ.copy()
    env["XCURSOR_THEME"] = "blank"
    env["XCURSOR_PATH"] = "/home/kiosk/.icons:/usr/share/icons"
    env["XCURSOR_SIZE"] = "1"
    return env


# Path MUST live inside the snap's allowed home — snap confinement blocks
# chromium from reading anything outside /home/kiosk/snap/chromium/.
_NO_CURSOR_EXT = "/home/kiosk/snap/chromium/common/chromium-extensions/no-cursor"


def _spawn_chromium(url, profile_name, wm_class, scale=1.0):
    profile_dir = f"/home/kiosk/snap/chromium/common/.config/chromium-{profile_name}"
    return subprocess.Popen([
        "/snap/bin/chromium",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        "--password-store=basic",
        "--force-renderer-accessibility",
        # Hide cursor on every page (no cursor = no link-hover preview bar).
        f"--load-extension={_NO_CURSOR_EXT}",
        f"--disable-extensions-except={_NO_CURSOR_EXT}",
        f"--class={wm_class}",
        f"--force-device-scale-factor={scale}",
        f"--user-data-dir={profile_dir}",
        f"--app={url}",
    ], env=_chromium_env())


def _launch_or_switch(url, mode, profile_name, wm_class, workspace, scale=1.0):
    """Core launch logic. If chromium for this class is alive AND the URL
    matches what's loaded, just switch to the workspace. Otherwise kill
    the existing (if any) and launch fresh."""
    cleanup_dead()
    if alive(wm_class) and current_urls.get(wm_class) == url:
        i3msg("workspace", "number", str(workspace))
        write_state(mode)
        return
    kill_proc(wm_class)
    procs[wm_class] = _spawn_chromium(url, profile_name, wm_class, scale=scale)
    current_urls[wm_class] = url
    write_state(mode)
    # i3 routes new window to the assigned workspace; switch view.
    i3msg("workspace", "number", str(workspace))


def launch_url(url, mode, profile_name):
    """Routing wrapper — STREAM goes to workspace 2, SERVICES to 4."""
    if mode.startswith("stream:"):
        return _launch_or_switch(url, mode, profile_name, STREAM_CLASS, 2)
    scale = 0.85 if mode == "service:ug" else 1.0
    return _launch_or_switch(url, mode, profile_name, SERVICE_CLASS, 4, scale=scale)


def launch_arcade():
    cleanup_dead()
    if alive("retroarch"):
        i3msg("workspace", "number", "3")
        write_state("arcade")
        return
    try:
        procs["retroarch"] = subprocess.Popen(["retroarch", "--fullscreen"])
        write_state("arcade")
        i3msg("workspace", "number", "3")
    except FileNotFoundError:
        pass


def quit_launcher(event=None):
    for cls in list(procs):
        kill_proc(cls)
    root.destroy()


def check_child():
    cleanup_dead()
    root.after(2000, check_child)


# ---------------------------------------------------------------------------
# Picker sheet (shared by STREAM and SERVICES).
# ---------------------------------------------------------------------------


def close_picker():
    global _picker_window
    if _picker_window is not None:
        try:
            _picker_window.destroy()
        except Exception:
            pass
        _picker_window = None


def show_picker(title, items, accent_fill, accent_outline):
    global _picker_window
    close_picker()
    win = tk.Toplevel(root)
    _picker_window = win
    win.overrideredirect(True)
    win.configure(bg="#0a0a0a", cursor="none")

    rows = len(items) + 1
    pad = 20
    row_h = 130
    row_gap = 18
    panel_w = 760
    panel_h = pad * 2 + rows * row_h + (rows - 1) * row_gap + 90

    x = (SCREEN_W - panel_w) // 2
    y = (SCREEN_H - panel_h) // 2
    win.geometry(f"{panel_w}x{panel_h}+{x}+{y}")

    cv = tk.Canvas(win, width=panel_w, height=panel_h,
                   bg="#0a0a0a", highlightthickness=2,
                   highlightbackground=accent_outline)
    cv.pack(fill="both", expand=True)

    cv.create_text(panel_w // 2, 50, text=title,
                   font=("DejaVu Sans", 32, "bold"),
                   fill=accent_outline)

    def add_row(idx, label, on_tap, fill, outline):
        cy = pad + 90 + idx * (row_h + row_gap) + row_h // 2
        x1 = pad
        x2 = panel_w - pad
        r = row_h // 2
        drawn = [
            cv.create_oval(x1, cy - r, x1 + 2 * r, cy + r,
                           fill=fill, outline=outline, width=3),
            cv.create_oval(x2 - 2 * r, cy - r, x2, cy + r,
                           fill=fill, outline=outline, width=3),
            cv.create_rectangle(x1 + r, cy - r, x2 - r, cy + r,
                                fill=fill, outline=""),
            cv.create_line(x1 + r, cy - r, x2 - r, cy - r,
                           fill=outline, width=3),
            cv.create_line(x1 + r, cy + r, x2 - r, cy + r,
                           fill=outline, width=3),
            cv.create_text(panel_w // 2, cy, text=label,
                           font=("DejaVu Sans", 32, "bold"), fill="#ffffff"),
        ]
        for it in drawn:
            cv.tag_bind(it, "<Button-1>", lambda e: on_tap())

    for idx, (label, url, mode, profile) in enumerate(items):
        def go(u=url, m=mode, p=profile):
            close_picker()
            launch_url(u, m, p)
        add_row(idx, label, go, accent_fill, accent_outline)
    add_row(len(items), "Cancel", close_picker, "#333333", "#888888")


def show_stream_picker():
    if len(STREAM_ITEMS) == 1:
        _, url, mode, profile = STREAM_ITEMS[0]
        launch_url(url, mode, profile)
        return
    show_picker("STREAM", STREAM_ITEMS, "#1e5f3a", "#5fff9f")


def show_services_picker():
    show_picker("SERVICES", SERVICE_ITEMS, "#1e3a5f", "#5f9fff")


# ---------------------------------------------------------------------------
# Root window
# ---------------------------------------------------------------------------

root = tk.Tk()
root.title("TIOSK")
root.configure(bg="#000000", cursor="none")
root.bind("<Escape>", quit_launcher)

SCREEN_W = root.winfo_screenwidth()
SCREEN_H = root.winfo_screenheight()
# NO overrideredirect — let i3 manage the window. The i3 config has
# a `for_window [title="^TIOSK$"]` rule that puts us on workspace 1
# fullscreen, so we get the right geometry without overrideredirect's
# "I'm on top of everything forever" downside.
root.geometry(f"{SCREEN_W}x{SCREEN_H}+0+0")

img = Image.open(WALLPAPER)
img_w, img_h = img.size
scale = max(SCREEN_W / img_w, SCREEN_H / img_h)
new_size = (int(img_w * scale), int(img_h * scale))
img = img.resize(new_size, Image.LANCZOS)
left = (img.size[0] - SCREEN_W) // 2
top = (img.size[1] - SCREEN_H) // 2
img = img.crop((left, top, left + SCREEN_W, top + SCREEN_H))
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
    canvas.create_oval(x1 + 4, y1 + 4, x1 + 2 * r + 4, y2 + 4,
                       fill="#000000", outline="")
    canvas.create_oval(x2 - 2 * r + 4, y1 + 4, x2 + 4, y2 + 4,
                       fill="#000000", outline="")
    canvas.create_rectangle(x1 + r + 4, y1 + 4, x2 - r + 4, y2 + 4,
                            fill="#000000", outline="")
    drawn = [
        canvas.create_oval(x1, y1, x1 + 2 * r, y2,
                           fill=fill, outline=accent, width=3),
        canvas.create_oval(x2 - 2 * r, y1, x2, y2,
                           fill=fill, outline=accent, width=3),
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2,
                                fill=fill, outline=""),
        canvas.create_line(x1 + r, y1, x2 - r, y1,
                           fill=accent, width=3),
        canvas.create_line(x1 + r, y2, x2 - r, y2,
                           fill=accent, width=3),
        canvas.create_text(cx, cy, text=label,
                           font=("DejaVu Sans", 36, "bold"),
                           fill="#ffffff"),
    ]
    for it in drawn:
        canvas.tag_bind(it, "<Button-1>", lambda e: command())


btn_y = SCREEN_H // 2 + 80
btn_w, btn_h = 360, 130
spacing = 60
total = 3 * btn_w + 2 * spacing
left_cx = (SCREEN_W - total) // 2 + btn_w // 2
mid_cx = left_cx + btn_w + spacing
right_cx = mid_cx + btn_w + spacing

make_pill(left_cx, btn_y, btn_w, btn_h, "STREAM",
          "#1e5f3a", "#5fff9f", show_stream_picker)
make_pill(mid_cx, btn_y, btn_w, btn_h, "ARCADE",
          "#5f1e3a", "#ff5fa8", launch_arcade)
make_pill(right_cx, btn_y, btn_w, btn_h, "SERVICES",
          "#1e3a5f", "#5f9fff", show_services_picker)

adopt_orphans_at_startup()
check_child()
root.mainloop()
