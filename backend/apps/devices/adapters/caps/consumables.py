from ..capability import Capability
from ..schema import PERCENT, obj, text

CAPABILITY = Capability(
    "consumables", "Material levels and runout.", targets=("machine",),
    events={"consumable.level": obj({"slot": text(32), "material": text(60), "remaining_percent": PERCENT},
                                    ["slot", "remaining_percent"]),
            "consumable.runout": obj({"slot": text(32), "material": text(60)}, ["slot"])},
)
