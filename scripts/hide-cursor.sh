#!/bin/bash
# TIOSK cursor blanker.
# Even with unclutter running, the X server briefly renders the cursor at the
# point of a touch event before unclutter hides it. The fix is to make the
# cursor image itself transparent at the server level so there is nothing to
# render in the first place.
#
# Creates a 1x1 transparent XBM and applies it as the root cursor, then
# shrinks the Xcursor theme to 1px so Qt/Gtk apps that fetch their own
# cursors from the theme also render nothing perceptible.

BLANK="/home/kiosk/.blank.xbm"

cat > "$BLANK" << 'EOF'
#define blank_width 1
#define blank_height 1
static unsigned char blank_bits[] = { 0x00 };
EOF

xsetroot -cursor "$BLANK" "$BLANK"

# Force theme cursors to 1px so app-level cursors disappear too.
echo "Xcursor.size: 1" | xrdb -merge
