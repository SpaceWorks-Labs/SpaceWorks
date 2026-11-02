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

from dataclasses import dataclass, field
from typing import Any, Callable

from django.core.exceptions import ValidationError

BOOL, INT, CHOICE, LIST = "bool", "int", "choice", "list"
KINDS = frozenset({BOOL, INT, CHOICE, LIST})
FEATURE, POLICY = "feature", "policy"
SPACE, STAFF_STRICTEST = "space", "staff_strictest"


def bool_stricter(a, b):
    return bool(a) or bool(b)


def higher_is_stricter(a, b):
    return max(a, b)


def lower_is_stricter(a, b):
    return min(a, b)


def bool_off_stricter(a, b):
    """For a permission (``..._allowed``): off is the stricter value."""
    return bool(a) and bool(b)


def zero_off_lower_stricter(a, b):
    """Lower is stricter, but 0 means "off" and is the loosest value."""
    if a == 0 or b == 0:
        return b if a == 0 else a
    return min(a, b)


def choice_stricter(order):
    """Order is loosest first; the later choice wins."""
    def stricter(a, b):
        return a if order.index(a) >= order.index(b) else b
    return stricter


@dataclass(frozen=True)
class SecuritySetting:
    key: str
    label: str
    kind: str
    default: Any
    stricter: Callable[[Any, Any], Any]
    storage: str = FEATURE
    description: str = ""
    choices: tuple = ()
    minimum: int | None = None
    maximum: int | None = None
    extra: dict = field(default_factory=dict)
    scope: str = SPACE

    def normalize(self, value):
        """Validate one incoming value and return it in canonical form."""
        if self.kind == BOOL:
            if type(value) is not bool:
                raise ValidationError(f"{self.label} takes true or false.", code="invalid_security_value")
            return value
        if self.kind == INT:
            if type(value) is not int:
                raise ValidationError(f"{self.label} takes a whole number.", code="invalid_security_value")
            if (self.minimum is not None and value < self.minimum) or (
                    self.maximum is not None and value > self.maximum):
                raise ValidationError(f"{self.label} is out of range.", code="invalid_security_value")
            return value
        if self.kind == CHOICE:
            if value not in self.choices:
                raise ValidationError(f"{self.label} takes one of {', '.join(map(str, self.choices))}.",
                                      code="invalid_security_value")
            return value
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValidationError(f"{self.label} takes a list of text values.", code="invalid_security_value")
        if len(value) > self.extra.get("max_items", 100):
            raise ValidationError(f"{self.label} has too many entries.", code="invalid_security_value")
        item = self.extra.get("normalize_item")
        try:
            return sorted({item(entry) if item else entry for entry in value})
        except ValueError as exc:
            raise ValidationError(f"{self.label}: {exc}", code="invalid_security_value") from exc

    def satisfies(self, value, floor):
        """True when ``value`` is at least as strict as ``floor``."""
        return self.stricter(value, floor) == value

    def normalize_floor(self, floor):
        floor = self.normalize(floor)
        strict = self.stricter(True, False) if self.kind == BOOL else None
        if self.kind == BOOL and floor is not strict:
            # Q9: a boolean lock forces the stricter value; the other would lock nothing.
            word = "on; send true" if strict else "off; send false"
            raise ValidationError(f"A lock on an on/off setting forces it {word}.",
                                  code="invalid_security_floor")
        return floor


# Release 2 retired ``security.staff_mfa_required``: staff MFA is mandatory everywhere
# (#62), so it is a fixed platform rule, not a setting. The login-security rows are
# appended here by the lane whose door honours them (accounts.login_security_settings).
from apps.accounts.login_security_settings import (  # noqa: E402 -- after SecuritySetting exists
    PASSKEYS_ALLOWED, STAFF_IDLE_TIMEOUT_MINUTES, STAFF_SESSION_MAX_HOURS,
)

REGISTRY = (
    PASSKEYS_ALLOWED,  # S-A: passkey ceremonies and the staff factor
    STAFF_SESSION_MAX_HOURS,  # S-A: staff routes (staff_session_policy)
    STAFF_IDLE_TIMEOUT_MINUTES,  # S-A: staff routes (staff_session_policy)
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
    return key in FEATURE_KEYS
