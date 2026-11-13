from ..capability import Capability
from ..schema import num, obj, text

# Remote config is a bounded JSON object owned by staff; the adapter polls `config` (or is woken) and acks the version.
ACK = obj({"version": num(1, 10 ** 9, "integer"), "outcome": {"type": "string", "enum": ["applied", "rejected"]},
           "detail": text(200)}, ["version", "outcome"])
CAPABILITY = Capability(
    "config.push", "Versioned adapter configuration pushed by staff and acknowledged by the adapter.",
    routes=("GET config", "POST config/ack"),
)
