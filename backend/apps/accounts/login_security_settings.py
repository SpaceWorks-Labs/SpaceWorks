"""The frozen per-space login-security settings (#128 C-2), re-exported by the contract.

Each row is a ``SecuritySetting`` for ``makerspaces.security_settings_registry``, stored
in the space's ``MakerspaceSecurityPolicy``. The enforcing lane appends a row to
``REGISTRY`` when its door honours it -- never earlier, so the panel never offers a
setting nothing enforces:

| key | kind | default | stricter | scope | lane |
| --- | --- | --- | --- | --- | --- |
| ``security.login_risk_check`` | bool | on | on | staff_strictest | S-B |
| ``security.remembered_device_days`` | int 1-90 | 90 (env) | lower | staff_strictest | S-B |
| ``security.staff_session_max_hours`` | int 1-720 | 168 | lower | staff_strictest | S-B |
| ``security.staff_idle_timeout_minutes`` | int 0-1440 | 0 (off) | lower, 0 loosest | staff_strictest | S-B |
| ``security.captcha_on_sign_in`` | choice | off | off < after_failures < always | space | S-C |
| ``security.passkeys_allowed`` | bool | on | off | staff_strictest | S-A |
| ``security.staff_ip_allowlist`` | list of CIDRs | [] (any) | narrower | space | S-C |

Every row is lockable by the superadmin (a floor, #111 Q9; a boolean lock forces the
stricter value). Passkeys are offered and never forced (#74): the setting can only take
them away. CAPTCHA applies on the space's verified custom domain only, to everyone signing
in there (#135 Q-A4); the IP allow-list applies to that space's staff routes only. Platform
deny rules and automatic blocks stay global in ``/control/``.
"""

import ipaddress

from apps.makerspaces.security_setting_types import (
    BOOL, CHOICE, INT, LIST, POLICY, SPACE, STAFF_STRICTEST, SecuritySetting,
    bool_off_stricter, bool_stricter, choice_stricter, lower_is_stricter, zero_off_lower_stricter,
)

CAPTCHA_CHOICES = ("off", "after_failures", "always")


def normalize_cidr(value):
    """One allow-list entry as a canonical network (``ValueError`` when it is not one)."""
    return str(ipaddress.ip_network(value.strip(), strict=False))


def _networks(values):
    return [ipaddress.ip_network(value, strict=False) for value in values]


def _within(inner, outer):
    return all(any(net.version == other.version and net.subnet_of(other) for other in _networks(outer))
               for net in _networks(inner))


def allowlist_stricter(a, b):
    """Empty means any address (loosest). Otherwise the list contained in the other wins;
    when neither contains the other the second argument (the floor) wins."""
    if not a or not b:
        return b if not a else a
    if _within(a, b):
        return a
    return b


LOGIN_RISK_CHECK = SecuritySetting(
    "security.login_risk_check", "Check unusual sign-ins", BOOL, True, bool_stricter,
    storage=POLICY, scope=STAFF_STRICTEST,
    description="A sign-in from a new device or network, or after failed attempts, needs a second check.",
)
REMEMBERED_DEVICE_DAYS = SecuritySetting(
    "security.remembered_device_days", "Remember a checked device for (days)", INT, 90, lower_is_stricter,
    storage=POLICY, scope=STAFF_STRICTEST, minimum=1, maximum=90,
    extra={"platform_setting": "LOGIN_REMEMBERED_DEVICE_DAYS"},
    description="After this many days a device must pass the unusual-sign-in check again.",
)
STAFF_SESSION_MAX_HOURS = SecuritySetting(
    "security.staff_session_max_hours", "Staff session length (hours)", INT, 168, lower_is_stricter,
    storage=POLICY, scope=STAFF_STRICTEST, minimum=1, maximum=720,
    description="Staff sign in again after this long, however active they are.",
)
STAFF_IDLE_TIMEOUT_MINUTES = SecuritySetting(
    "security.staff_idle_timeout_minutes", "Staff idle timeout (minutes)", INT, 0, zero_off_lower_stricter,
    storage=POLICY, scope=STAFF_STRICTEST, minimum=0, maximum=1440,
    description="Staff are signed out after this long without activity; 0 turns it off.",
)
CAPTCHA_ON_SIGN_IN = SecuritySetting(
    "security.captcha_on_sign_in", "CAPTCHA on sign-in", CHOICE, "off", choice_stricter(CAPTCHA_CHOICES),
    storage=POLICY, scope=SPACE, choices=CAPTCHA_CHOICES,
    description="On this space's verified domain: never, after failed attempts, or always.",
)
PASSKEYS_ALLOWED = SecuritySetting(
    "security.passkeys_allowed", "Allow passkeys", BOOL, True, bool_off_stricter,
    storage=POLICY, scope=STAFF_STRICTEST,
    description="Staff may use a passkey instead of an authenticator code. Passkeys are never required.",
)
STAFF_IP_ALLOWLIST = SecuritySetting(
    "security.staff_ip_allowlist", "Staff IP allow-list", LIST, [], allowlist_stricter,
    storage=POLICY, scope=SPACE, extra={"normalize_item": normalize_cidr, "max_items": 100},
    description="Staff screens of this space work only from these networks; empty allows any.",
)

PER_SPACE_SETTINGS = (
    LOGIN_RISK_CHECK, REMEMBERED_DEVICE_DAYS, STAFF_SESSION_MAX_HOURS, STAFF_IDLE_TIMEOUT_MINUTES,
    CAPTCHA_ON_SIGN_IN, PASSKEYS_ALLOWED, STAFF_IP_ALLOWLIST,
)
