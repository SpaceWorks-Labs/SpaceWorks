"""Whether passkeys may be used by one person right now.

Two switches, both able only to take passkeys away (they are never forced, #74): the
platform ``PlatformLoginMethods.passkeys_enabled`` (fail-open read, default on) and the
per-space ``security.passkeys_allowed``, resolved as the strictest value across the
spaces where the person holds a staff role (#128 C-2; off is stricter and a superadmin
lock forces it off, #157). A person whose spaces disallow passkeys must use the
authenticator: their passkeys stop signing them in and stop counting as their staff
factor, but are never deleted. A failed policy read refuses (fail closed).
"""

import logging

from rest_framework import status
from rest_framework.exceptions import APIException

from apps.accounts.login_security_contract import PASSKEYS_ALLOWED, PASSKEYS_UNAVAILABLE

logger = logging.getLogger(__name__)


class PasskeysUnavailable(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = PASSKEYS_UNAVAILABLE

    def __init__(self, detail="Passkeys are turned off for this account. Use your authenticator app."):
        super().__init__({"detail": detail, "code": PASSKEYS_UNAVAILABLE})


def passkeys_usable(user):
    from apps.accounts.login_methods import passkeys_enabled
    if not passkeys_enabled():
        return False
    from apps.makerspaces.security_settings_person import strictest_for_staff
    try:
        return bool(strictest_for_staff(user, PASSKEYS_ALLOWED))
    except Exception:
        logger.exception("passkeys_allowed_unreadable", extra={"user_id": getattr(user, "pk", None)})
        return False


def assert_usable(user):
    if not passkeys_usable(user):
        raise PasskeysUnavailable()
