from ..capability import Capability
from ..schema import num, obj

NUMBERS = {"type": "object", "additionalProperties": num(-100000, 100000)}
CAPABILITY = Capability(
    "telemetry", "Optional numeric readings (temperatures, metrics) alongside a status report.",
    status_props={"telemetry": obj({"temperatures": NUMBERS, "metrics": NUMBERS})}, routes=("POST status",),
)
