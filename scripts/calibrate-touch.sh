#!/bin/bash
# Apply touch calibration matrix every session start
# Retry a few times in case device isn't ready immediately
for i in 1 2 3 4 5; do
    if xinput list 2>/dev/null | grep -q "Elo TouchSystems"; then
        DEVICE_ID=$(xinput list --id-only "EloTouchSystems,Inc Elo TouchSystems 2216 AccuTouch® USB Touchmonitor Interface" 2>/dev/null)
        if [ -z "$DEVICE_ID" ]; then
            # Fallback: find by partial name
            DEVICE_ID=$(xinput list 2>/dev/null | grep -i "Elo TouchSystems" | grep -oP 'id=\K[0-9]+' | head -1)
        fi
        if [ -n "$DEVICE_ID" ]; then
            xinput set-prop "$DEVICE_ID" "Coordinate Transformation Matrix" 1.1933 0 -0.0811 0 -1.2317 1.1156 0 0 1
            echo "$(date) Applied calibration to device $DEVICE_ID" >> /tmp/touch-cal.log
            exit 0
        fi
    fi
    sleep 1
done
echo "$(date) FAILED to find Elo device" >> /tmp/touch-cal.log
exit 1
