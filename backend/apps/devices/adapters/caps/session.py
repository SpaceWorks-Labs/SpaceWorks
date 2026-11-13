from ..capability import Capability
from ..schema import UUID, num, obj
from .access_authorize import CREDENTIAL

# `event_id` (decision 342) is optional and advisory: linked only when the session's member may act for that
# event in this space, ignored otherwise. It never changes the access decision or fails the session.
START = obj({"binding_id": UUID, "credential": CREDENTIAL, "event_id": num(1, 2 ** 53, "integer")},
            ["binding_id", "credential"])
STOP = obj({"reason": {"type": "string", "enum": ["member", "device", "idle"]},
            "active_minutes": num(0, 10 ** 5, "integer"), "idle_minutes": num(0, 10 ** 5, "integer")})
CAPABILITY = Capability(
    "session.start", "Start a metered machine session through the machine-session service.",
    targets=("machine",), routes=("POST sessions/start",),
)
CAPABILITY_STOP = Capability("session.stop", "Stop a live session the adapter started.", targets=("machine",),
                             routes=("POST sessions/{id}/stop",))
