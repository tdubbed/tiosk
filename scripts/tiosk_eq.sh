#!/bin/bash
# TIOSK EQ preset switcher.
# Usage: tiosk_eq.sh <flat|bass|vocal>
#
# Implements EQ via PipeWire filter-chain. Writes a config file to
# ~/.config/pipewire/pipewire.conf.d/99-tiosk-eq.conf and restarts the
# user PipeWire service so the new chain is loaded. Brief audio glitch
# during the swap (sub-second).
#
# Presets:
#   flat   — pass-through, no EQ
#   bass   — +6dB shelf at 80Hz, slight cut at 1kHz
#   vocal  — slight cut at 300Hz, +4dB peak at 2.5kHz for clarity

set -e

PRESET="${1:-flat}"
CFG_DIR="${HOME}/.config/pipewire/pipewire.conf.d"
CFG_FILE="${CFG_DIR}/99-tiosk-eq.conf"
mkdir -p "$CFG_DIR"

write_flat() {
    # No filter-chain at all — just delete the config so audio is direct.
    rm -f "$CFG_FILE"
}

write_bass() {
    cat > "$CFG_FILE" << 'EOF'
context.modules = [
    { name = libpipewire-module-filter-chain
      args = {
          node.description = "TIOSK EQ (Bass Boost)"
          media.name       = "TIOSK EQ"
          filter.graph = {
              nodes = [
                  { type = builtin label = bq_lowshelf
                    name = LowShelfL control = { Freq = 80  Q = 0.7 Gain = 6 } }
                  { type = builtin label = bq_peaking
                    name = MidL      control = { Freq = 1000 Q = 1.0 Gain = -2 } }
                  { type = builtin label = bq_lowshelf
                    name = LowShelfR control = { Freq = 80  Q = 0.7 Gain = 6 } }
                  { type = builtin label = bq_peaking
                    name = MidR      control = { Freq = 1000 Q = 1.0 Gain = -2 } }
              ]
              links = [
                  { output = "LowShelfL:Out" input = "MidL:In" }
                  { output = "LowShelfR:Out" input = "MidR:In" }
              ]
              inputs  = [ "LowShelfL:In" "LowShelfR:In" ]
              outputs = [ "MidL:Out"     "MidR:Out"     ]
          }
          capture.props = {
              node.name      = "tiosk_eq_in"
              media.class    = Audio/Sink
              audio.position = [ FL FR ]
          }
          playback.props = {
              node.name      = "tiosk_eq_out"
              audio.position = [ FL FR ]
              node.passive   = true
          }
      } }
]
EOF
}

write_vocal() {
    cat > "$CFG_FILE" << 'EOF'
context.modules = [
    { name = libpipewire-module-filter-chain
      args = {
          node.description = "TIOSK EQ (Vocal)"
          media.name       = "TIOSK EQ"
          filter.graph = {
              nodes = [
                  { type = builtin label = bq_peaking
                    name = LowMidL  control = { Freq = 300  Q = 1.0 Gain = -3 } }
                  { type = builtin label = bq_peaking
                    name = PresenceL control = { Freq = 2500 Q = 1.2 Gain = 4 } }
                  { type = builtin label = bq_peaking
                    name = LowMidR  control = { Freq = 300  Q = 1.0 Gain = -3 } }
                  { type = builtin label = bq_peaking
                    name = PresenceR control = { Freq = 2500 Q = 1.2 Gain = 4 } }
              ]
              links = [
                  { output = "LowMidL:Out" input = "PresenceL:In" }
                  { output = "LowMidR:Out" input = "PresenceR:In" }
              ]
              inputs  = [ "LowMidL:In"  "LowMidR:In"  ]
              outputs = [ "PresenceL:Out" "PresenceR:Out" ]
          }
          capture.props = {
              node.name      = "tiosk_eq_in"
              media.class    = Audio/Sink
              audio.position = [ FL FR ]
          }
          playback.props = {
              node.name      = "tiosk_eq_out"
              audio.position = [ FL FR ]
              node.passive   = true
          }
      } }
]
EOF
}

case "$PRESET" in
    flat)  write_flat ;;
    bass)  write_bass ;;
    vocal) write_vocal ;;
    *) echo "Unknown preset: $PRESET" >&2; exit 1 ;;
esac

# Restart user PipeWire so the new (or absent) filter-chain takes effect.
systemctl --user restart pipewire pipewire-pulse wireplumber 2>/dev/null || true

# Mono remap sink may have been wiped by the restart; re-apply.
sleep 1
/home/kiosk/tiosk_mono_audio.sh 2>/dev/null || true

echo "EQ preset applied: $PRESET"
