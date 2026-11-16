from ..capability import Capability
from ..schema import CODE, obj, text

CAPABILITY = Capability(
    "maintenance.report", "A fault goes to the existing maintenance workflow.", targets=("machine",),
    events={"maintenance.fault": obj({"code": CODE, "detail": text(300),
                                      "severity": {"type": "string", "enum": ["info", "warning", "fault"]}},
                                     ["code", "severity"])},
)
