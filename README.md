# TIOSK

A self-contained touchscreen jukebox + arcade kiosk built on Xubuntu.

## Hardware

- **Chassis:** Repurposed Kiosk Information Systems pedestal (former Samuel U. Rodgers Health Center community kiosk)
- **PC:** Dell OptiPlex 5040 SFF — i5-6500, 16 GB DDR4, M.2 NVMe
- **Display:** 1280×1024 Elo TouchSystems 2216 AccuTouch (single-touch resistive)
- **Networking:** Ethernet to home LAN (.105), WoL enabled (MAC 48:4d:7e:d1:64:eb)

## Software stack

- **Base OS:** Xubuntu 26.04 LTS (X11 + LightDM)
- **Browser:** Qiosk (Qt WebEngine, integrated Qt Virtual Keyboard for touch input)
- **Music server:** Mopidy with Iris web UI; library sourced from NAS-T `/mnt/storage/tdrive/media/music_clean`
- **Emulation:** RetroArch (libretro)
- **Launcher:** Custom Tkinter (`scripts/tiosk_launcher.py`)
- **HUD:** Floating collapsible volume + home button overlay (`scripts/tiosk_volume_hud.py`)
- **Cursor:** unclutter-xfixes (hide on touch)

## Architecture

- Auto-login as `kiosk` user → XFCE → autostart fires launcher + HUD + touch calibration
- HUD is always-on-top; collapses to a single `≡` button at bottom-left
- JUKEBOX → Qiosk fullscreen at Iris (persistent profile so login + setup survive)
- ARCADE → RetroArch fullscreen
- HOME button on HUD gracefully kills any running fullscreen app and returns to launcher

## Touchscreen calibration

Live matrix: `1.1933 0 -0.0811 0 -1.2317 1.1156`

Persisted via xorg.conf.d InputClass (`config/xorg-touch-calibration.conf`) and a startup script fallback.

## Install (fresh Xubuntu)

See `install.sh`. Bootstrap requires only:
1. Fresh Xubuntu 26.04 install with user `terrence`
2. `sudo apt install -y openssh-server` and add SSH pubkey
3. `sudo bash install.sh`

## File layout

```
scripts/    Python + bash for launcher, HUD, calibration
config/     System config files (mopidy, lightdm, xorg)
autostart/  Desktop entries for XFCE autostart
assets/     Wallpaper, future image assets
docs/       Architecture notes, tuning cheatsheets
```

## Known issues / future

- Qt Virtual Keyboard's keyboard-down button doesn't reliably hide the keyboard (dismiss by tapping outside the input)
- Wallpaper hardcoded to one nebula; future: rotate wallpapers
- Streaming services (Amazon Music, YouTube Music) and Recipes pending integration as additional launcher options
