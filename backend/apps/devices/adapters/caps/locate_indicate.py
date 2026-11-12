from ..capability import Capability
from ..schema import num, obj, text

# Staff-only. A storage location, item or box NEVER reaches a public surface; the command params
# carry only an opaque binding handle plus the saved pose (see locate_calibrate), never a name.
CAPABILITY = Capability(
    "locate.indicate", "Point at or light up a storage location, item or box. Staff only; never public.",
    targets=("space", "storage_location", "item", "box"),  # a pointer is bound to the area it covers
    commands={"indicate": obj({"mode": {"type": "string", "enum": ["point", "light", "clear"]},
                               "duration_seconds": num(1, 600, "integer"), "pose": {"type": "object"},
                               "color": text(16)}, ["mode"])},
)
