"""Primitives for emailed 6-digit codes (lane S0); the flows that send them live elsewhere.

U-C (merge proofs, #65) and S-B (unusual-login codes, #62) both build on these. A code is
never stored: only ``digest(code, purpose, subject)``, an HMAC-SHA256 under a key derived
from ``SECRET_KEY`` and the purpose, so a digest from one purpose or subject never
verifies another. ``verify`` compares in constant time. TTL and attempt caps are plain
helpers so each flow keeps its own row and its own audit.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

DIGITS = 6
MAX_ATTEMPTS = 5
_SALT = "spaceworks.accounts.login_codes.v1:"


def new_code():
    """Six uniformly random digits from the OS CSPRNG."""
    return f"{secrets.randbelow(10 ** DIGITS):0{DIGITS}d}"


def normalize(code):
    """The six digits a person typed (spaces and dashes ignored), or ``None``."""
    if not isinstance(code, str):
        return None
    digits = code.replace(" ", "").replace("-", "")
    if len(digits) != DIGITS or not digits.isascii() or not digits.isdigit():
        return None
    return digits


def _label(name, value):
    value = str(value)
    if not value or "\x00" in value:
        raise ValueError(f"A login-code {name} must be non-empty text.")
    return value


def digest(code, purpose, subject):
    """Hex HMAC-SHA256 of the code, bound to ``purpose`` and ``subject`` (e.g. a user or
    challenge id). Raises ``ValueError`` for a code that is not six digits."""
    clean = normalize(code)
    if clean is None:
        raise ValueError("A login code is six digits.")
    key_salt = _SALT + _label("purpose", purpose)
    return salted_hmac(key_salt, f"{_label('subject', subject)}\x00{clean}", algorithm="sha256").hexdigest()


def verify(stored, code, purpose, subject):
    """True only when ``code`` produces ``stored`` for this purpose and subject.

    Malformed input is a plain mismatch; the comparison is constant time."""
    if not stored or normalize(code) is None:
        return False
    return constant_time_compare(stored, digest(code, purpose, subject))


def expires_at(now=None, ttl_seconds=None):
    """When a code issued ``now`` stops working (``LOGIN_CODE_TTL_SECONDS`` by default)."""
    ttl = settings.LOGIN_CODE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    return (now or timezone.now()) + timedelta(seconds=ttl)


def is_expired(expiry, now=None):
    return expiry is None or (now or timezone.now()) >= expiry


def attempts_exhausted(attempts, cap=MAX_ATTEMPTS):
    """True once ``attempts`` failed checks have used the cap; the code is then dead."""
    return attempts >= cap


def attempts_left(attempts, cap=MAX_ATTEMPTS):
    return max(cap - attempts, 0)
