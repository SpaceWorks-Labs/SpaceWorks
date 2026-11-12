"""Refuse passwords found in known breaches (#62, #66): HIBP k-anonymity, fail-open.

``BreachedPasswordValidator`` sits in ``AUTH_PASSWORD_VALIDATORS``, so every path that
calls ``validate_password`` runs it: sign-up, password change, reset and restore
confirmation, staff invitation acceptance, admin-set passwords and the ``/control/``
reset form. Only the first five hex characters of the password's SHA-1 leave the server
(``GET https://api.pwnedpasswords.com/range/<prefix>`` with ``Add-Padding: true``); the
match is made locally against the returned suffixes. Any failure to ask (timeout, network,
a non-200 answer) lets the password through, because an outage of a third party must
never stop someone changing a password. ``PASSWORD_BREACH_CHECK_ENABLED`` turns it off.
"""

from django.utils.translation import gettext_lazy
import hashlib
import logging

import httpx
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.accounts.login_security_contract import PASSWORD_BREACHED

logger = logging.getLogger(__name__)
RANGE_URL = "https://api.pwnedpasswords.com/range/{prefix}"
MESSAGE = (gettext_lazy("This password has appeared in a data breach, so it is not safe to use. "
           "Choose a different password."))


def _transport():
    """Tests replace this with an ``httpx.MockTransport``; production uses the network."""
    return None


def breach_count(password):
    """How often the password appears in known breaches; None when the check could not run."""
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()  # noqa: S324 -- the HIBP protocol
    prefix, suffix = digest[:5], digest[5:]
    try:
        with httpx.Client(timeout=settings.PASSWORD_BREACH_CHECK_TIMEOUT_SECONDS, transport=_transport()) as client:
            response = client.get(RANGE_URL.format(prefix=prefix),
                                  headers={"Add-Padding": "true", "User-Agent": "SpaceWorks-password-check"})
    except httpx.HTTPError:
        logger.warning("password_breach_check_unavailable")
        return None
    if response.status_code != 200:
        logger.warning("password_breach_check_unavailable", extra={"status": response.status_code})
        return None
    for line in response.text.splitlines():
        candidate, _, count = line.strip().partition(":")
        if candidate.upper() == suffix:
            try:
                return int(count)  # padding rows carry a count of 0
            except ValueError:
                return 0
    return 0


class BreachedPasswordValidator:
    def validate(self, password, user=None):
        if not settings.PASSWORD_BREACH_CHECK_ENABLED or not password:
            return
        if not breach_count(password):
            return
        from apps.audit import services as audit

        # The validator cannot know who typed the password (a person, or an admin setting
        # someone's), so the row names the account it was for and no actor.
        audit.record(None, "auth.password_breach_rejected", target=user if getattr(user, "pk", None) else None)
        raise ValidationError(MESSAGE, code=PASSWORD_BREACHED)

    def get_help_text(self):
        return "Your password can't be one that has appeared in a known data breach."


def is_breached(exc):
    """True when a Django ``ValidationError`` from ``validate_password`` includes a breach."""
    return any(getattr(error, "code", None) == PASSWORD_BREACHED for error in getattr(exc, "error_list", []))


def error_body(field, exc):
    """The 400 body for a refused password: messages under ``field``, plus
    ``code: password_breached`` when the breach check refused it."""
    body = {field: list(exc.messages)}
    if is_breached(exc):
        body["code"] = PASSWORD_BREACHED
    return body
