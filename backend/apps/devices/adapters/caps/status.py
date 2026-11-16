from ..capability import STATES, Capability
from ..schema import CODE, PERCENT, num, obj, text

# Fabman-derived vocabulary (FABMAN-RESEARCH 9.1): typed fault codes the server maps to notifications.
ERROR_CODES = ("thermal_runaway", "filament_runout", "door_open", "emergency_stop", "filter_alert", "comms_lost",
               "hardware_fault", "unknown")
BOOL = {"type": "boolean"}

CAPABILITY = Capability(
    "status", "Bounded, normalised state of each bound target, sent on a heartbeat-like report.",
    status_props={
        "state": {"type": "string", "enum": list(STATES)}, "progress_percent": PERCENT,
        "eta_seconds": num(0, 31536000, "integer"), "error_code": CODE, "error_detail": text(200),
        "area_clear": BOOL, "busy": BOOL, "power": {"type": "string", "enum": ["on", "off", "unknown"]},
        "error_codes": {"type": "array", "maxItems": 8, "items": {"type": "string", "enum": list(ERROR_CODES)}},
        "interlocks": obj({"enclosure_closed": {"type": ["boolean", "null"]}, "filter_ok": {"type": ["boolean", "null"]},
                           "estop_ok": {"type": ["boolean", "null"]}}),
        "session_ref": text(64), "clear_token": text(64),
    },
    routes=("POST status",),
)
