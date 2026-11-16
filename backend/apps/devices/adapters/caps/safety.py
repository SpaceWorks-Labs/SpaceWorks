from ..capability import Capability
from ..schema import num, obj

# Per machine-type or per-binding config; the SERVER enforces it, the adapter only reports.
PROFILE = obj({"auto_off_idle_minutes": num(1, 1440, "integer"), "require_area_clear": {"type": "boolean"},
               "max_session_minutes": num(1, 1440, "integer"), "require_filter_ok": {"type": "boolean"}})
# A binding's own config adds the per-binding auto-apply switch (never inherited from a type profile).
# Shelf pointers add two hard caps (decision 331): the server clamps every indicate to them; `clear` is never capped.
CONFIG = obj({**PROFILE["properties"], "auto_apply_terminal": {"type": "boolean"},
              "laser_max_power_pct": num(1, 100, "integer"), "max_on_seconds": num(1, 600, "integer")})
CAPABILITY = Capability(
    "safety", "Server-enforced idle auto-off, area-clear confirmation and max session length.",
    targets=("machine",), events={"safety.area_cleared": obj({"confirmed": {"type": "boolean"}}, ["confirmed"])},
)
