"""Published pose kinds for shelf pointers (decision 331 addendum).

A pose is the small flat JSON object a staff member saved for one storage location, item or box, and the server hands
it back to the owning adapter inside a ``locate.indicate`` (or ``aim``) command. A pose that names a ``kind`` is
validated against the schema below when it is saved, so a Raspberry Pi, an ESP32 or any other adapter can rely on the
shape. A pose with NO ``kind`` stays free-form (the adapter's own ``calibration_schema``). An unknown ``kind`` is
refused: that is how a typo is told apart from a deliberate private pose.

The calibration maths (homography, servo offsets, per-shelf angle tables) stays on the adapter: the server stores only
the resulting pose, never reference points.
"""
from ..schema import PERCENT, num, obj, text

KIND = "kind"
# Laser kinds: these can put light into a room, so the server also clamps ``laser_power_pct`` and the on-time.
LASER_KINDS = ("pan_tilt", "galvo_xy")

PAN_TILT = obj({
    KIND: {"type": "string", "enum": ["pan_tilt"]},
    "pan_deg": num(-180, 180), "tilt_deg": num(-180, 180), "laser_power_pct": PERCENT,
}, [KIND, "pan_deg", "tilt_deg"])

# Normalised scanner coordinates: -1..1 spans the adapter's own calibrated field (DAC full scale is adapter-local).
GALVO_XY = obj({
    KIND: {"type": "string", "enum": ["galvo_xy"]},
    "x": num(-1, 1), "y": num(-1, 1), "laser_power_pct": PERCENT,
}, [KIND, "x", "y"])

# A run of pixels on a pick-to-light strip (WS2812-style). ``color`` is a name or "#rrggbb".
LED_SEGMENT = obj({
    KIND: {"type": "string", "enum": ["led_segment"]},
    "strip": num(0, 15, "integer"), "start": num(0, 4095, "integer"), "count": num(1, 512, "integer"),
    "color": text(16),
}, [KIND, "strip", "start", "count"])

POSE_KINDS = {"pan_tilt": PAN_TILT, "galvo_xy": GALVO_XY, "led_segment": LED_SEGMENT}
