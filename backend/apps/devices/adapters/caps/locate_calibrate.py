from ..capability import Capability
from ..schema import UUID, obj, text

# The pose is device-specific coordinates: opaque JSON validated against the schema the adapter
# declares in its hello (`calibration_schema`). Poses are staff data and never leave staff surfaces.
POSE = {"type": "object"}
CAPABILITY = Capability(
    "locate.calibrate", "Calibrate a pointer: jog/aim, stream position, save a pose per location, bin or item.",
    targets=("space", "storage_location", "item", "box"),  # a pointer is bound to the area it covers
    commands={"aim": obj({"pose": POSE}, ["pose"]), "jog": obj({"dx": {"type": "number"}, "dy": {"type": "number"}})},
    events={"calibration.position": obj({"session_id": UUID, "pose": POSE}, ["session_id", "pose"])},
    routes=("POST calibration/{session_id}/position",),
)
CALIBRATION_HELLO = obj({"calibration_schema": {"type": "object"}})
SAVE = obj({"pose": POSE, "note": text(80)}, ["pose"])
