#!/bin/bash
# TIOSK cursor blanker.
#
# Touch events still flash the cursor because Qt/Chromium widgets set their
# own cursor per-window, ignoring xsetroot's root cursor. The only fix that
# works everywhere is a fully-transparent Xcursor theme that Qt resolves to
# instead of the system default.
#
# This script:
#   1. Builds a "blank" Xcursor theme in /home/kiosk/.icons/blank
#   2. Sets it as the default via xrdb + ~/.config/gtk-3.0/settings.ini
#   3. Sets a transparent root cursor via xsetroot for non-Qt windows
#
# Qiosk is also launched with XCURSOR_THEME=blank by the launcher.

set -e

THEME_DIR="/home/kiosk/.icons/blank"
BLANK_PNG="/tmp/tiosk_blank.png"
BLANK_CFG="/tmp/tiosk_blank.cfg"
BLANK_XBM="/home/kiosk/.blank.xbm"

# ---- 1x1 transparent PNG (decoded from base64 — RGBA all zero) ----
python3 -c "
from PIL import Image
img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
img.save('$BLANK_PNG')
"

# ---- Generate Xcursor file from the transparent PNG ----
mkdir -p "$THEME_DIR/cursors"
echo "32 0 0 $BLANK_PNG" > "$BLANK_CFG"
xcursorgen "$BLANK_CFG" "$THEME_DIR/cursors/left_ptr"

# Symlink every standard cursor name to the same blank file.
cd "$THEME_DIR/cursors"
for name in default arrow xterm hand2 watch question_arrow crosshair fleur \
            sb_h_double_arrow sb_v_double_arrow text pointer wait progress \
            cell vertical-text alias copy no-drop not-allowed grab grabbing \
            all-scroll col-resize row-resize n-resize e-resize s-resize w-resize \
            ne-resize nw-resize se-resize sw-resize ew-resize ns-resize \
            nesw-resize nwse-resize zoom-in zoom-out help link move dnd-none \
            dnd-copy dnd-move dnd-link dnd-no-drop top_left_corner \
            top_right_corner bottom_left_corner bottom_right_corner \
            top_side bottom_side left_side right_side; do
    ln -sf left_ptr "$name"
done

# ---- Theme metadata ----
cat > "$THEME_DIR/index.theme" << 'EOF'
[Icon Theme]
Name=blank
Comment=Fully transparent cursor theme for kiosk use
EOF

cat > "$THEME_DIR/cursor.theme" << 'EOF'
[Icon Theme]
Inherits=blank
EOF

# ---- GTK settings ----
mkdir -p /home/kiosk/.config/gtk-3.0
cat > /home/kiosk/.config/gtk-3.0/settings.ini << 'EOF'
[Settings]
gtk-cursor-theme-name=blank
gtk-cursor-theme-size=1
EOF

# ---- Apply now via xrdb (theme + size) ----
{
    echo "Xcursor.theme: blank"
    echo "Xcursor.size: 1"
    echo "Xcursor.theme_core: 1"
} | xrdb -merge

# ---- Root cursor blank XBM (for the rare app that hits the root window) ----
cat > "$BLANK_XBM" << 'EOF'
#define blank_width 8
#define blank_height 8
#define blank_x_hot 0
#define blank_y_hot 0
static unsigned char blank_bits[] = {
   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
EOF
xsetroot -cursor "$BLANK_XBM" "$BLANK_XBM"

echo "Blank cursor theme applied."
