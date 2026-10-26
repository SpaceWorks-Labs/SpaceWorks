"""Per-space security settings and the order that makes one value stricter than another.

One row per setting. The registry is the single list the service, the platform lock, the
pre-save guard, the staff API and the /control/ page all read, so a new security setting
is added here and nowhere else (release 2's login-security lane adds its rows here).

Storage decides where a value lives:
- ``feature``: a key in ``Makerspace.enabled_features``; present means on (bool only).
- ``policy``: a value in the per-space policy table release 2 adds. No row uses it yet,
  and the service refuses it until that table exists.

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


def bool_stricter(a, b):
    return bool(a) or bool(b)


def higher_is_stricter(a, b):
    return max(a, b)


def lower_is_stricter(a, b):
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
        return sorted(set(value))

    def satisfies(self, value, floor):
        """True when ``value`` is at least as strict as ``floor``."""
        return self.stricter(value, floor) == value

    def normalize_floor(self, floor):
        floor = self.normalize(floor)
        if self.kind == BOOL and floor is not True:
            # Q9: a boolean lock means "forced on". A false floor would lock nothing.
            raise ValidationError("A lock on an on/off setting forces it on; send true.",
                                  code="invalid_security_floor")
        return floor


REGISTRY = (
    SecuritySetting(
        "security.staff_mfa_required", "Require MFA for staff", BOOL, False, bool_stricter,
        storage=FEATURE,
        description="Staff with actions in this space must enroll in an authenticator (TOTP) app.",
    ),
)
BY_KEY = {setting.key: setting for setting in REGISTRY}
FEATURE_KEYS = frozenset(setting.key for setting in REGISTRY if setting.storage == FEATURE)

assert all(setting.kind in KINDS and setting.storage in {FEATURE, POLICY} for setting in REGISTRY)
assert all(setting.kind == BOOL for setting in REGISTRY if setting.storage == FEATURE)


def get(key):
    setting = BY_KEY.get(key)
    if setting is None:
        raise ValidationError("Unknown security setting.", code="unknown_security_setting")
    return setting


def stored_value(makerspace, key):
    """The value as stored on the row; ``feature`` storage is presence in enabled_features."""
    setting = get(key)
    if setting.storage == FEATURE:
        return key in set(makerspace.enabled_features or [])
    raise ValidationError("This setting's storage is not available yet.", code="security_storage_unavailable")


def is_security_feature(key):
    return key in FEATURE_KEYS
