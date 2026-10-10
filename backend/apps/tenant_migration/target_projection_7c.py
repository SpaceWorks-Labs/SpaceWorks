"""Cancel the delivery substrate even when only label models are selected.

Parent delivery is permanently inert, while label outcomes/receipts remain historical.
These rules agree with 7b's generic command projection; there is no result replay.
"""


def label_projections(field_type):
    reason = "Imported label commands cannot restart physical printing."
    return {
        ("devices.DeviceCommand", "status"): field_type("cancelled", reason=reason),
        ("devices.DeviceCommand", "lease_token_digest"): field_type(None, reason=reason),
        ("devices.DeviceCommand", "lease_expires_at"): field_type(None, reason=reason),
        ("devices.DeviceCommand", "acknowledged_at"): field_type(None, reason=reason),
    }
