"""Reading the login-method switches, and refusing the ones that would lock people out.

Two halves that must not be confused with each other:

* the **reads**, used at each login boundary, which fail **OPEN** -- a broken capability
  lookup must never be the reason nobody can sign in. Every other capability read on an
  auth path does the same.
* the **lockout guards**, used by the `/control/` form, which are the opposite: they
  refuse a change whenever they cannot prove it is survivable. Switching a method off is
  the dangerous direction, and the accounts it strands are exactly the ones
  forgot-password cannot recover, because they have no usable password to reset.

`login_methods_validation` owns the complete proposed-state check shared by the admin
form, installer and management command. The query helpers here retain their existing
interfaces; configured provider availability includes the install-time choices.
"""

import logging

from django.core.cache import cache
from django.db.models import Exists, OuterRef

from apps.accounts.models import PlatformLoginMethods, User
from apps.accounts.models_social import SocialIdentity
from apps.accounts.social_staff_providers import staff_capable_provider_filter

logger = logging.getLogger(__name__)

LOGIN_METHODS_CACHE_KEY = "accounts:login_methods:last_known_good:v1"
_SWITCH_FIELDS = (
    "password_enabled",
    "social_enabled",
    "phone_enabled",
    "self_registration_enabled",
    "mfa_enabled",
    "google_enabled",
    "apple_enabled",
    "github_enabled",
)


def _values(switches):
    return {field: bool(getattr(switches, field)) for field in _SWITCH_FIELDS}


def _cached_switches():
    try:
        values = cache.get(LOGIN_METHODS_CACHE_KEY)
    except Exception:  # pragma: no cover - a cache outage must not block authentication
        logger.exception("login_methods_cache_read_failed")
        return None
    if values is None:
        return None
    return PlatformLoginMethods(**values)


def _switches():
    try:
        switches = PlatformLoginMethods.load()
    except Exception:
        logger.exception("login_methods_read_failed")
        return _cached_switches() or PlatformLoginMethods()

    try:
        cache.set(LOGIN_METHODS_CACHE_KEY, _values(switches), timeout=None)
    except Exception:  # pragma: no cover - preserve the successfully resolved policy
        logger.exception("login_methods_cache_write_failed")
    return switches


def password_login_enabled():
    return bool(_switches().password_enabled)


def mfa_login_enabled():
    return bool(_switches().mfa_enabled)


def social_login_enabled():
    """Covers the built-ins AND every configured OIDC provider.

    Built-ins additionally need their install-time choice and configured credentials;
    OIDC providers retain their own `is_enabled` and readiness checks.
    """
    return bool(_switches().social_enabled)


def provider_login_enabled(provider):
    """Install-time built-in choice AND social master; OIDC keeps its row switch."""
    switches = _switches()
    return bool(switches.social_enabled and (
        getattr(switches, f"{provider}_enabled")
        if provider in ("google", "apple", "github") else str(provider).startswith("oidc:")
    ))


def phone_login_enabled():
    return bool(_switches().phone_enabled)


def self_registration_enabled():
    return bool(_switches().self_registration_enabled)


def users_stranded_without_social():
    """Active users whose only credential is a social identity.

    The per-provider check in `social_lockout` cannot answer this: someone holding both
    Google and Apple survives either provider being cleared and is stranded by social
    being switched off entirely.

    `has_usable_password()` inspects the hash prefix and is not expressible in SQL, so
    the query narrows to users who hold any social identity -- a bounded set -- and the
    final check runs in Python.
    """
    candidates = User.objects.filter(is_active=True).filter(
        Exists(SocialIdentity.objects.filter(user=OuterRef("pk")))
    )
    return [user for user in candidates if not user.has_usable_password()]


def superadmins_without_social():
    """Active superadmins holding no social identity.

    With passwords switched off these are the accounts that cannot sign in — and only if
    social sign-in itself stays enabled, which is why the caller checks that first rather
    than this function trying to know both switches at once.

    Narrowed to superadmins on purpose. A member or a staffer stranded by this can be
    recovered by an administrator; an administrator stranded by it cannot be recovered by
    anyone, and `/control/` is the only place the switch can be flipped back. Same floor
    that stops `superadmin_access_enabled` being turned off without Platform Email
    configured: never remove the last route back in.

    Phone is not counted as a rescue. It signs in on the **member surface only** -- the
    refresh claim is a hardcoded "member" and staff surfaces reject it -- so a superadmin
    holding only a verified number still cannot reach the console.
    """
    superadmins = User.objects.filter(is_active=True).filter(
        is_superuser=True
    ) | User.objects.filter(is_active=True, role=User.Role.SUPERADMIN)
    from apps.accounts.login_methods_validation import available_providers

    available = available_providers(PlatformLoginMethods.load())
    superadmins = superadmins.distinct().annotate(
        has_social=Exists(SocialIdentity.objects.filter(
            staff_capable_provider_filter(), user=OuterRef("pk"), provider__in=available
        ))
    )
    return [user for user in superadmins if not user.has_social]
