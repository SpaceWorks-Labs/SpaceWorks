from ..capability import Capability
from ..schema import CODE, UUID, num, obj, text

HEALTH = obj({"health": {"type": "string", "enum": ["ok", "degraded", "failing"]}, "firmware": text(40),
              "uptime_seconds": num(0, 10 ** 9, "integer"), "last_error": CODE})
CAPABILITY = Capability(
    "diagnostics", "Adapter health, firmware and version in status, and a staff-requested log bundle upload.",
    targets=("machine", "door", "space", "storage_location"),
    status_props={"diagnostics": HEALTH},
    commands={"log_bundle": obj({"command_ref": UUID, "max_bytes": num(1024, 10 * 2 ** 20, "integer"),
                                 "since_seconds": num(60, 7 * 86400, "integer")}, ["max_bytes"])},
    switch="machines.integrations.diagnostics",
)
