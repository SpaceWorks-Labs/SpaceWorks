"""Query-free redaction for domain QR payloads; available in bookings-only installs."""
import re

_BOOKING_QR = re.compile(r"spaceworks-booking:[0-9a-fA-F-]{36}")


def redact_confirmation_credentials(value):
    return _BOOKING_QR.sub("spaceworks-booking:[redacted]", value)
