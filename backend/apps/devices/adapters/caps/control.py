from ..capability import Capability
from ..schema import obj

CAPABILITY = Capability(
    "control", "Staff-initiated controls delivered by command lease/ack/result.",
    targets=("machine", "door", "space"),
    commands={"pause": obj({}), "resume": obj({}), "cancel": obj({}),
              "power": obj({"on": {"type": "boolean"}}, ["on"])},
)
