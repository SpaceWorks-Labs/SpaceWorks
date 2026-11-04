"""Per-space security settings and the order that makes one value stricter than another.

One row per setting. The registry is the single list the service, the platform lock, the
pre-save guard, the staff API and the /control/ page all read, so a new security setting
is added here and nowhere else (release 2's login-security lane adds its rows here).

Storage decides where a value lives:
- ``feature``: a key in ``Makerspace.enabled_features``; present means on (bool only).
- ``policy``: a key in ``MakerspaceSecurityPolicy.values`` (one row per space); absent
  means the row's ``default``. Any kind.

Scope decides who a value applies to (#128 C-2):
- ``space``: this space's own surfaces (its staff routes, its verified domain);
- ``staff_strictest``: a person, as the strictest value across every space where they
  hold a staff role (``security_settings_person.strictest_for_staff``).

``stricter(a, b)`` returns whichever of two valid values is the stricter one. A platform
lock is a floor (owner decision #111 Q9): a space may only choose values at least as
strict as the floor, and a boolean lock means "forced on".
"""

from django.core.exceptions import ValidationError

from .security_setting_types import (  # noqa: F401 -- re-exported
    BOOL, CHOICE, FEATURE, INT, KINDS, LIST, POLICY, SPACE, STAFF_STRICTEST, SecuritySetting,
    bool_off_stricter, bool_stricter, choice_stricter, higher_is_stricter, lower_is_stricter,
    zero_off_lower_stricter,
)

# Release 2 retired ``security.staff_mfa_required``: staff MFA is mandatory everywhere
# (#62), so it is a fixed platform rule, not a setting. The login-security rows are
# appended here by the lane whose door honours them (accounts.login_security_settings).
from apps.accounts.login_security_settings import (
    CAPTCHA_ON_SIGN_IN, LOGIN_RISK_CHECK, PASSKEYS_ALLOWED, REMEMBERED_DEVICE_DAYS, STAFF_IDLE_TIMEOUT_MINUTES,
    STAFF_IP_ALLOWLIST, STAFF_SESSION_MAX_HOURS,
)

REGISTRY = (
    PASSKEYS_ALLOWED,  # S-A: passkey ceremonies and the staff factor
    STAFF_SESSION_MAX_HOURS,  # S-A: staff routes (staff_session_policy)
    STAFF_IDLE_TIMEOUT_MINUTES,  # S-A: staff routes (staff_session_policy)
    CAPTCHA_ON_SIGN_IN,  # S-C: Turnstile on the space's verified domain (accounts.turnstile)
    STAFF_IP_ALLOWLIST,  # S-C: the space's staff routes (accounts.staff_network)
    LOGIN_RISK_CHECK,  # S-B: the unusual-sign-in step-up at every password door (accounts.login_risk)
    REMEMBERED_DEVICE_DAYS,  # S-B: how long a device is remembered (accounts.device_memory)
)
BY_KEY = {setting.key: setting for setting in REGISTRY}
FEATURE_KEYS = frozenset(setting.key for setting in REGISTRY if setting.storage == FEATURE)

POLICY_KEYS = frozenset(setting.key for setting in REGISTRY if setting.storage == POLICY)

assert all(setting.kind in KINDS and setting.storage in {FEATURE, POLICY}
           and setting.scope in {SPACE, STAFF_STRICTEST} for setting in REGISTRY)
assert all(setting.kind == BOOL for setting in REGISTRY if setting.storage == FEATURE)


def get(key):
    setting = BY_KEY.get(key)
    if setting is None:
        raise ValidationError("Unknown security setting.", code="unknown_security_setting")
    return setting


def stored_value(makerspace, key, policy_values=None):
    """The value as stored; ``feature`` is presence in enabled_features, ``policy`` the
    space's policy row (``policy_values`` when the caller already read it)."""
    setting = get(key)
    if setting.storage == FEATURE:
        return key in set(makerspace.enabled_features or [])
    if policy_values is None:
        from .security_policy_store import policy_values as read
        policy_values = read(makerspace)
    return policy_value(setting, policy_values)


def policy_value(setting, values):
    """One setting out of a policy ``values`` dict; a missing or unreadable entry is the
    default (the store only ever writes normalized values)."""
    if setting.key not in (values or {}):
        return setting.default
    try:
        return setting.normalize(values[setting.key])
    except ValidationError:
        return setting.default


def is_security_feature(key):
    """Any ``security.*`` key: only the security service writes it, and it is never a
    module setting, a setup answer or a delegable grant (#111 Q10/Q11)."""
    return key in BY_KEY or str(key).startswith("security.")
