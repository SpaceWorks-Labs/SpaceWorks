"""Staff session length and idle timeout (#110c, #128 C-2; defaults #157: 168 h, idle off).

A browser session stamps ``auth_time`` when it signs in. For a person holding a staff
role, every mint and rotation also stamps ``staff_until``: the moment staff routes stop
accepting this session. It is the earlier of ``auth_time`` + the strictest
``security.staff_session_max_hours`` across the person's staff spaces and, when
``security.staff_idle_timeout_minutes`` is on and the refresh arrives after a longer
gap, the refresh itself. Once passed it never moves later.

Only staff routes look at it (``staff_identity.require_staff_mfa``): an expired staff
session is still a member session, never a sign-out of member features. Native device
grants keep their own lifecycle (attested, role-bound, revocable) and carry no
``staff_until``. Idle time is measured between refreshes, so it is accurate to about
one access-token lifetime.
"""

from django.utils.translation import gettext
import logging
import time

from rest_framework.exceptions import PermissionDenied

from apps.accounts.login_security_contract import (
    STAFF_IDLE_TIMEOUT_MINUTES, STAFF_SESSION_EXPIRED, STAFF_SESSION_MAX_HOURS,
)

logger = logging.getLogger(__name__)
AUTH_TIME, STAFF_UNTIL = "auth_time", "staff_until"


def _now():
    return int(time.time())


def limits(user):
    """``(max_hours, idle_minutes)``, the strictest across the person's staff spaces."""
    from apps.makerspaces.security_settings_person import strictest_for_staff
    try:
        return (strictest_for_staff(user, STAFF_SESSION_MAX_HOURS),
                strictest_for_staff(user, STAFF_IDLE_TIMEOUT_MINUTES))
    except Exception:  # a broken read still bounds the session: the platform defaults
        logger.exception("staff_session_limits_unreadable", extra={"user_id": getattr(user, "pk", None)})
        return STAFF_SESSION_MAX_HOURS.default, STAFF_IDLE_TIMEOUT_MINUTES.default


def _is_device(token):
    return bool(token.get("device_grant_id"))


def _stamp(user, token, now, idle_from):
    from apps.accounts.staff_identity import has_staff_role
    if _is_device(token) or not has_staff_role(user):
        token.payload.pop(STAFF_UNTIL, None)
        return
    max_hours, idle_minutes = limits(user)
    auth_time = int(token.get(AUTH_TIME) or token.get("iat") or now)
    until = auth_time + max_hours * 3600
    if token.get(STAFF_UNTIL) is not None:
        until = min(until, int(token[STAFF_UNTIL]))
    if idle_minutes and idle_from is not None and now - int(idle_from) > idle_minutes * 60:
        until = min(until, now)
    token[STAFF_UNTIL] = until


def stamp_new(user, token):
    """A fresh sign-in: the session starts now."""
    now = _now()
    token[AUTH_TIME] = now
    _stamp(user, token, now, idle_from=None)


def stamp_rotated(user, refresh, previous_iat):
    """A refresh: ``previous_iat`` is when the presented refresh token was minted."""
    _stamp(user, refresh, _now(), idle_from=previous_iat)


def assert_staff_session(user, claims):
    """Refuse a staff route once this browser session's staff time is up."""
    if claims is None or _is_device(claims):
        return
    until = claims.get(STAFF_UNTIL)
    if until is None:
        # Minted before the person held a staff role: judge it live until it rotates.
        started = claims.get(AUTH_TIME) or claims.get("iat")
        if not started:
            return
        until = int(started) + limits(user)[0] * 3600
    if _now() >= int(until):
        raise PermissionDenied({"detail": gettext("Your staff session has ended. Sign in again to use staff screens."),
                                "code": STAFF_SESSION_EXPIRED})
