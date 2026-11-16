"""Remembered devices for the unusual-login check (#62, Q12, Q13; lane S-B).

A browser carries the ``sw_device`` cookie, a native app the same value as
``device_trust`` (returned on every device sign-in, sent back in the ``X-Device-Trust``
header). Either is ``signing.dumps({"d": <128-bit hex>}, salt="accounts.device")``; the
database keeps only ``KnownDevice.device_hmac``, a keyed HMAC of ``d``, so a stolen table
names no device. A row is created or slid forward only when a sign-in COMPLETES; refresh
and device grants never touch it.

A remembered device only answers "has this person signed in here before". It never lets
anyone skip a second factor (Q13): staff still pass TOTP or a passkey at every sign-in.
The window is ``security.remembered_device_days``, the strictest across the person's staff
spaces (members: ``LOGIN_REMEMBERED_DEVICE_DAYS``).
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.accounts.login_security_contract import DEVICE_COOKIE, REMEMBERED_DEVICE_DAYS

logger = logging.getLogger(__name__)
SALT = "accounts.device"
_HMAC_SALT = "spaceworks.accounts.device_memory.v1"
COOKIE_MAX_AGE = 400 * 86400
HEADER = "HTTP_X_DEVICE_TRUST"
_PENDING = "_sw_device_token"


def _raw(request):
    cookies = getattr(request, "COOKIES", None) or {}
    meta = getattr(request, "META", None) or {}
    return cookies.get(DEVICE_COOKIE) or meta.get(HEADER) or ""


def device_id(request):
    """The 128-bit device value of a valid presented cookie or trust token, else None."""
    raw = _raw(request)
    if not raw or len(raw) > 512:
        return None
    try:
        value = signing.loads(raw, salt=SALT, max_age=COOKIE_MAX_AGE).get("d")
    except (signing.BadSignature, AttributeError, TypeError, ValueError):
        return None
    return value if isinstance(value, str) and len(value) == 32 else None


def device_hmac(value):
    return salted_hmac(_HMAC_SALT, value, algorithm="sha256").hexdigest()


def remembered_days(user=None):
    if user is None or getattr(user, "pk", None) is None:
        return settings.LOGIN_REMEMBERED_DEVICE_DAYS
    from apps.makerspaces.security_settings_person import strictest_for_staff
    try:
        return int(strictest_for_staff(user, REMEMBERED_DEVICE_DAYS))
    except Exception:  # a broken read still bounds memory: the platform default
        logger.warning("remembered_device_days_unreadable", exc_info=True)
        return settings.LOGIN_REMEMBERED_DEVICE_DAYS


def lookup(request, user=None):
    """The live ``KnownDevice`` the request's cookie/trust token names (for ``user`` when
    given), inside the remembered-device window; None otherwise."""
    from apps.accounts.models import KnownDevice
    value = device_id(request)
    if value is None:
        return None
    rows = KnownDevice.objects.filter(device_hmac=device_hmac(value), revoked_at__isnull=True)
    if user is not None:
        rows = rows.filter(user_id=user.pk)
    fresh = timezone.now() - timedelta(days=remembered_days(user))
    return rows.filter(last_verified_at__gte=fresh).order_by("-last_verified_at").first()


def ua_label(request):
    """A coarse, non-identifying label such as "Firefox on Windows"."""
    agent = (getattr(request, "META", None) or {}).get("HTTP_USER_AGENT", "")[:512]
    browser = next((name for token, name in (
        ("SpaceWorks", "Space Works app"), ("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"),
        ("Chrome/", "Chrome"), ("Safari/", "Safari")) if token in agent), "A browser")
    system = next((name for token, name in (
        ("Android", "Android"), ("iPhone", "iOS"), ("iPad", "iPadOS"), ("Windows", "Windows"),
        ("Mac OS X", "macOS"), ("CrOS", "ChromeOS"), ("Linux", "Linux")) if token in agent), "")
    return (f"{browser} on {system}" if system else browser)[:120]


def remember(request, user):
    """Record a completed sign-in on this device. Returns ``(row, token, created)``:
    ``token`` is the value to set as the cookie or return as ``device_trust``."""
    from apps.accounts.models import KnownDevice
    now = timezone.now()
    value = device_id(request)
    row = None
    if value is not None:
        row = KnownDevice.objects.filter(user_id=user.pk, device_hmac=device_hmac(value)).first()
        if row is not None and row.revoked_at is not None:
            value, row = None, None  # a forgotten device starts again under a new value
    created = False
    if row is None:
        value = value or secrets.token_hex(16)
        row, created = KnownDevice.objects.get_or_create(
            user_id=user.pk, device_hmac=device_hmac(value),
            defaults={"ua_label": ua_label(request), "last_verified_at": now})
    if not created:
        KnownDevice.objects.filter(pk=row.pk).update(last_verified_at=now, ua_label=ua_label(request))
    return row, signing.dumps({"d": value}, salt=SALT), created


def stash(request, token):
    """Hand a web view the cookie value to set (see ``attach``)."""
    setattr(getattr(request, "_request", request), _PENDING, token)


def attach(response, request):
    """Set the remembered-device cookie a completed web sign-in stashed, if any."""
    token = getattr(getattr(request, "_request", request), _PENDING, None)
    if token:
        # The refresh cookie's SameSite/Secure policy (None + Secure by default), so a split
        # deployment whose console and API are cross-site still sends it on sign-in.
        response.set_cookie(DEVICE_COOKIE, token, max_age=COOKIE_MAX_AGE, httponly=True,
                            secure=settings.AUTH_COOKIE_SECURE, samesite=settings.AUTH_COOKIE_SAMESITE,
                            path=settings.AUTH_COOKIE_PATH)
    return response


def live_devices(user):
    from apps.accounts.models import KnownDevice
    return KnownDevice.objects.filter(user_id=user.pk, revoked_at__isnull=True).order_by("-last_verified_at")


def forget(user, device_pk, *, request=None):
    """Revoke one of the person's own devices; False when it is not theirs or already gone."""
    from apps.accounts import audit_events
    from apps.accounts.models import KnownDevice
    now = timezone.now()
    changed = KnownDevice.objects.filter(pk=device_pk, user_id=user.pk, revoked_at__isnull=True).update(revoked_at=now)
    if changed:
        audit_events.record_auth_event(user, "auth.device_forgotten", target=user)
    return bool(changed)


def revoke_all(user, *, now=None, keep=None):
    """Revoke every remembered device (logout-all, password change/reset, not-me)."""
    from apps.accounts.models import KnownDevice
    rows = KnownDevice.objects.filter(user_id=user.pk, revoked_at__isnull=True)
    if keep is not None:
        rows = rows.exclude(pk=keep.pk)
    return rows.update(revoked_at=now or timezone.now())


def restore(row):
    """Undo a blanket revocation for the one device that made a password change."""
    from apps.accounts.models import KnownDevice
    if row is not None:
        KnownDevice.objects.filter(pk=row.pk).update(revoked_at=None, last_verified_at=timezone.now())
