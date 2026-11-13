from ..capability import Capability
from ..schema import UUID, num, obj, text

KINDS = ("failure", "spaghetti", "fire", "smoke", "person", "other")
CAPABILITY = Capability(
    "detection.report", "A detection (failure, fire, smoke, person...) with confidence and an evidence frame. Notifies; never acts.",
    targets=("machine", "door", "space"),
    events={"detection.reported": obj({
        "kind": {"type": "string", "enum": list(KINDS)}, "confidence": num(0, 1),
        "artifact_id": UUID, "note": text(200)}, ["kind", "confidence"])},
    switch="machines.integrations.detections",
)
