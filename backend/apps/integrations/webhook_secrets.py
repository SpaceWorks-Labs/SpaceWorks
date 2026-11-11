"""Server-generated, shown-once signing secrets for signed webhooks, with rotation (parity E-B8, A10).

The secret is generated here, returned to the staff member exactly once by the create/rotate response, and stored
only as Fernet ciphertext; no API ever reads it back. Rotating moves the current secret to
``previous_signing_secret`` for a grace window and the signature header carries one ``v1=`` value per live secret
(newest first), so a receiver can deploy the new secret before the old one stops verifying. A grace of 0 retires
the old secret immediately.
"""

import secrets
from datetime import timedelta

from django.utils import timezone

SECRET_PREFIX = "whsec_"
DEFAULT_GRACE_HOURS = 24
MAX_GRACE_HOURS = 168


def generate_signing_secret() -> str:
    return SECRET_PREFIX + secrets.token_urlsafe(32)


def rotate_signing_secret(destination, *, grace_hours=DEFAULT_GRACE_HOURS, now=None) -> str:
    """Install a new secret on ``destination`` (caller saves) and return it, the only time it is ever visible."""
    now = now or timezone.now()
    current = destination.get_signing_secret()
    if current and grace_hours > 0:
        destination.set_previous_signing_secret(current)
        destination.previous_secret_valid_until = now + timedelta(hours=grace_hours)
    else:
        clear_previous(destination)
    fresh = generate_signing_secret()
    destination.set_signing_secret(fresh)
    return fresh


def clear_previous(destination) -> None:
    destination.previous_signing_secret = ""
    destination.previous_secret_valid_until = None


def live_previous_secret(destination, now=None) -> str:
    """The retiring secret while its grace window is open, else ""."""
    until = destination.previous_secret_valid_until
    if not destination.previous_signing_secret or until is None or until <= (now or timezone.now()):
        return ""
    return destination.get_previous_signing_secret()
