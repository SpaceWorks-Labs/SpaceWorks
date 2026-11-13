from ..capability import Capability
from ..schema import UUID, obj, text

# One still, base64 (about 512 KiB raw at most). Held in the cache for a minute, never written to storage.
FRAME = obj({"content_type": {"type": "string", "enum": ["image/jpeg"]}, "data": text(700000, minLength=4)},
            ["content_type", "data"])
CAPABILITY = Capability(
    "media.snapshot", "A JPEG still, uploaded only while someone is watching (fallback for media.stream).",
    targets=("machine", "door", "space"),
    commands={"snapshot": obj({"watch_id": UUID}, ["watch_id"])}, routes=("POST media/{watch_id}/snapshot",),
    switch="machines.integrations.video",
)
