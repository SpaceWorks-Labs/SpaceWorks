"""Explicit response union: a honeypot never invents a booking identity.

The status-only branch is closed so a real response cannot match both branches.
"""
BOOKING_SUBMISSION_RESPONSE = {
    "oneOf": [
        {
            "type": "object", "additionalProperties": False,
            "properties": {"status": {"type": "string", "enum": ["pending", "confirmed"]}},
            "required": ["status"],
        },
        {
            "type": "object", "additionalProperties": False,
            "properties": {
                "status": {"type": "string", "enum": ["pending", "confirmed"]},
                "public_token": {"type": "string", "format": "uuid"},
                "confirmation_available": {"type": "boolean"},
                "amount_due": {"type": "string", "nullable": True},
                "currency": {"type": "string", "nullable": True},
                "pay_online": {"type": "boolean"},
            },
            "required": ["status", "public_token", "confirmation_available", "amount_due", "currency", "pay_online"],
        },
    ],
}
