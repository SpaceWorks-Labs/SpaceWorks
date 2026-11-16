"""The push envelope (decision 310 addendum): a typed, content-free wake-up. Pure Python (no Django)."""
from .schema import EPOCH, UUID, num, obj, text

EVENT_TYPES = ("command.queued", "job.queued", "config.changed", "ping")
# ``data`` is present only when staff opted in to ``include_data``: capability and command NAMES, never parameters.
ENVELOPE = obj({
    "id": UUID, "type": {"type": "string", "enum": list(EVENT_TYPES)}, "api_version": num(1, 1, "integer"),
    "device_id": UUID, "binding_id": {"type": ["string", "null"], "format": "uuid"}, "created_at": EPOCH,
    "data": obj({"capability": text(32), "command": text(32)}, ["capability"]),
}, ["id", "type", "api_version", "device_id", "created_at"])
