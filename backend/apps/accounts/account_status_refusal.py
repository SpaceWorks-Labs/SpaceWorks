"""Typed 401 for a signed-in account that staff restricted or suspended (decision 355).

Web and native sessions both stop working the moment `access_status` leaves ACTIVE. Without
a code, a phone app cannot tell "your account was suspended" from "your session expired",
so it loops the person back to a sign-in that will fail. Only the bearer of an otherwise
valid token reaches this, so naming their own account state reveals nothing to anyone else;
the pre-auth sign-in doors keep their uniform answers (no enumeration).
"""
from django.utils.translation import gettext
from rest_framework.exceptions import AuthenticationFailed

ACCOUNT_STATUS_CODES = {"restricted": "account_restricted", "suspended": "account_suspended"}


def account_refusal(user, detail):
    """The 401 to raise: typed when the account itself is restricted or suspended."""
    code = ACCOUNT_STATUS_CODES.get(getattr(user, "access_status", None))
    if code is None:
        return AuthenticationFailed(detail)
    message = (gettext("Your account is restricted. Contact the makerspace to restore access.")
               if code == "account_restricted" else gettext("Your account is suspended."))
    # A dict detail is returned as the body, so clients get the typed `code` (DRF drops it otherwise).
    return AuthenticationFailed({"detail": message, "code": code})
