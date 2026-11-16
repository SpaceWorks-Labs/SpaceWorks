from ..capability import Capability
from ..schema import CODE, EPOCH, UUID, num, obj
from .job_dispatch import CONSUMPTION

LOG = obj({"operation_id": UUID, "binding_id": UUID, "session_id": num(1, 2 ** 62, "integer"),
           "started_at": EPOCH, "ended_at": EPOCH, "active_minutes": num(0, 10 ** 5, "integer"),
           "idle_minutes": num(0, 10 ** 5, "integer"),
           "outcome": {"type": "string", "enum": ["completed", "failed", "stopped", "timeout"]},
           "error_code": CODE, "stop_reason": {"type": "string", "enum": ["member", "staff", "device", "max_length", "idle_timeout", "deadman", "offline", "interlock", "closing"]}, "consumptions": {"type": "array", "items": CONSUMPTION, "maxItems": 32}},
          ["operation_id", "binding_id", "started_at", "ended_at", "active_minutes", "idle_minutes", "outcome"])
CAPABILITY = Capability(
    "usage.log", "One immutable usage record per session or job; feeds reports and the charge ledger.",
    targets=("machine",), routes=("POST usage",), switch="machines.integrations.usage_billing",
)
