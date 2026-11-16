from ..capability import Capability
from ..schema import CODE, obj, text

CAPABILITY = Capability(
    "events", "Typed, append-only events, idempotent by operation id.",
    events={
        "adapter.note": obj({"message": text(200)}, ["message"]),
        "adapter.error": obj({"code": CODE, "detail": text(200)}, ["code"]),
    },
    routes=("POST events",),
)
