"""The value types of per-space security settings and their strictness orders.

Split from ``security_settings_registry`` so the frozen login-security rows
(``accounts.login_security_settings``) and the registry that lists them never import each
other. Import these names from the registry; it re-exports them.
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
