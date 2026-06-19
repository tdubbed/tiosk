# T-OSK Manual Edit Guide

A reference for editing the kiosk launcher and HUD by hand, without needing Claude.

---

## The mental model

Two separate Python programs run on the kiosk:

| File | What it controls |
|---|---|
| `tiosk_launcher.py` | The main menu — wallpaper, title, the three pill buttons, and what happens when you tap one. |
| `tiosk_volume_hud.py` | The always-on-top overlay — the `≡` button that opens into volume +/-/Mute and the 🏠 HOME button. |

There is **one source of truth**: the GitHub repo at `github.com/tdubbed/tiosk`. The kiosk pulls from there. Editing files directly on the kiosk works for one boot, then `tiosk-deploy` overwrites them. So always edit the repo.

---

## Where things live

**On TPro (your code box) — the working copy:**
```
/tmp/tiosk-repo/
```
This is where Claude edits. You can `cd /tmp/tiosk-repo` and edit there too.

**On the kiosk — the running copy:**
```
/opt/tiosk/          ← cloned from GitHub
/home/kiosk/         ← deployed scripts get installed here
```

**On GitHub — the canonical history:**
```
github.com/tdubbed/tiosk
```

---

## The edit-and-deploy loop

```bash
# 1. Open the file you want to change (on TPro)
nano /tmp/tiosk-repo/scripts/tiosk_launcher.py

# 2. Commit and push to GitHub
cd /tmp/tiosk-repo
git add scripts/tiosk_launcher.py
git commit -m "what you changed"
git push origin main

# 3. Pull and apply on the kiosk
ssh TIOSK 'sudo tiosk-deploy'
```

`tiosk-deploy` pulls from GitHub, copies files into place, kills the running launcher + HUD, and relaunches them. Changes show up immediately — no reboot needed.

If you change touchscreen calibration or login behavior, use `sudo tiosk-deploy --restart-x` instead (it reboots).

---

## Common edits

### Change the title text
File: `scripts/tiosk_launcher.py`
Look for:
```python
canvas.create_text(SCREEN_W // 2, title_y, text="T-OSK", ...)
```
Change `"T-OSK"` to whatever you want. Both lines (the shadow and the main) — search for the title text and you'll find two occurrences.

### Change a button label
File: `scripts/tiosk_launcher.py`
Look for the `make_pill(...)` calls near the bottom:
```python
make_pill(left_cx, btn_y, btn_w, btn_h, "JUKEBOX", "#1e3a5f", "#5fa8ff", launch_jukebox)
make_pill(mid_cx,  btn_y, btn_w, btn_h, "STREAM",  "#1e5f3a", "#5fff9f", launch_stream)
make_pill(right_cx, btn_y, btn_w, btn_h, "ARCADE",  "#5f1e3a", "#ff5fa8", launch_arcade)
```
The 5th argument is the label. The 6th is the fill color. The 7th is the accent (border + edges).

### Change a button color
Same line as above. Format is `#RRGGBB` hex.
- 6th argument = fill color (the inside of the pill)
- 7th argument = accent color (the border + edge glow)

### Change where a button points (URL or app)
File: `scripts/tiosk_launcher.py`
Find the matching `launch_jukebox()`, `launch_stream()`, `launch_arcade()` function.
For STREAM, change the URL here:
```python
subprocess.Popen(["qiosk", "-f", "--profile-name", "stream",
                  "https://music.youtube.com/"], env=env)
```

### Change the wallpaper
Replace the file at `assets/wallpaper.jpg` in the repo. Same name. Commit, push, deploy. It auto-installs to `/home/kiosk/wallpaper.jpg` on the kiosk.

### Move the HUD position
File: `scripts/tiosk_volume_hud.py`
Look near the top:
```python
W_COLLAPSED = 60
H_COLLAPSED = 60
W_EXPANDED = 110
H_EXPANDED = 360
X = 10
Y_COLLAPSED = SCREEN_H - H_COLLAPSED - 10
```
- `X` is distance from the left edge. Make it larger to push right.
- `Y_COLLAPSED` is where the small button lives. The default puts it 10 px above the bottom.

### Change HUD button labels or behavior
File: `scripts/tiosk_volume_hud.py`
Look for the `tk.Button(...)` calls under "Expanded: full controls + close" — those are the volume up, mute, volume down, and home buttons. The `text="..."` arg is what shows; the `command=...` arg is what runs when tapped.

### Change what HOME does
File: `scripts/tiosk_volume_hud.py`
Find `def go_home():`. Currently it lowers the active app window and raises the launcher (so audio survives). If you want HOME to also kill the app, add `subprocess.run(["pkill", "-f", "qiosk"])` etc.

---

## Testing without rebooting

After `sudo tiosk-deploy`, the launcher and HUD restart automatically. Just look at the screen. If something looks wrong, edit and redeploy.

If the launcher won't start at all, check the log:
```bash
ssh TIOSK 'tail -50 /home/kiosk/launcher.log'
ssh TIOSK 'tail -50 /home/kiosk/hud.log'
```
Python errors will be obvious.

---

## Rolling back if you break something

Every deploy is a git commit. To undo the most recent change:

```bash
cd /tmp/tiosk-repo
git log --oneline -10        # find the commit before the bad one
git revert HEAD              # creates a new commit that undoes the last one
git push origin main
ssh TIOSK 'sudo tiosk-deploy'
```

Or to wipe local edits before committing:
```bash
cd /tmp/tiosk-repo
git checkout -- scripts/tiosk_launcher.py
```

---

## Files you generally don't need to touch

| File | What it is |
|---|---|
| `install.sh` | Only run on a fresh OS. Re-installing isn't reversible — leave it alone. |
| `deploy.sh` | The plumbing. Don't edit unless you're changing how deploys work. |
| `config/xorg-touch-calibration.conf` | Touchscreen calibration matrix. Only edit if calibration drifts. Requires `--restart-x` to apply. |
| `config/lightdm-autologin.conf` | Auto-login config. Don't touch. |
| `config/mopidy.conf` | Mopidy music server config. Editable, but rare. |
| `scripts/hide-cursor.sh` | Cursor blanker. Working fine — leave it. |

---

## Quick cheat sheet

| Want to | Edit | Then |
|---|---|---|
| Change title | `tiosk_launcher.py` → search for current title | commit, push, `tiosk-deploy` |
| Add a 4th button | `tiosk_launcher.py` → add a `make_pill(...)` + a `launch_X()` function | commit, push, `tiosk-deploy` |
| Change wallpaper | replace `assets/wallpaper.jpg` | commit, push, `tiosk-deploy` |
| Move HUD | `tiosk_volume_hud.py` → `X` and `Y_COLLAPSED` | commit, push, `tiosk-deploy` |
| See what's running | `ssh TIOSK 'pgrep -af tiosk_'` | — |
| See errors | `ssh TIOSK 'tail -50 /home/kiosk/launcher.log'` | — |
| Reboot the kiosk | `ssh TIOSK 'sudo systemctl reboot -i'` | — |
| Shut it down | `ssh TIOSK 'sudo systemctl poweroff -i'` | — |
| Roll back the last change | `cd /tmp/tiosk-repo && git revert HEAD && git push && ssh TIOSK 'sudo tiosk-deploy'` | — |
