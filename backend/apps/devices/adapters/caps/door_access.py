from ..capability import Capability
from ..schema import num, obj

CAPABILITY = Capability(
    "door.access", "Door and space entry: authorise via access.authorize, unlock by command, report door events.",
    targets=("door", "space"),
    commands={"unlock": obj({"seconds": num(1, 120, "integer")}, ["seconds"])},
    events={"door.opened": obj({}), "door.closed": obj({}), "door.forced": obj({})},
    switch="machines.integrations.access",
)
