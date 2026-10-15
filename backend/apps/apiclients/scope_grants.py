from dataclasses import dataclass

from apps.accounts import rbac
from apps.accounts.models import User
from apps.apiclients.scope_registry import (
    LEGACY_SCOPE,
    PUBLIC_ALL,
    PUBLIC_READ,
    PUBLIC_WRITE,
    SCOPE_VOCABULARY,
)


TENANT_GRANTABLE_SCOPES = frozenset({PUBLIC_READ, PUBLIC_WRITE})
SUPERADMIN_ONLY_SCOPES = SCOPE_VOCABULARY - TENANT_GRANTABLE_SCOPES


@dataclass(frozen=True, slots=True)
class ScopeGrantOption:
    value: str
    label: str
    description: str
    group: str


_CATALOG = (
    ScopeGrantOption(
        PUBLIC_READ, "Public read", "Read registered public API routes.", "Public API"
    ),
    ScopeGrantOption(
        PUBLIC_WRITE,
        "Public write",
        "Submit to registered public API routes.",
        "Public API",
    ),
    ScopeGrantOption(
        PUBLIC_ALL,
        "All public access",
        "Read and write every registered public route, including future routes.",
        "Operator-only",
    ),
    ScopeGrantOption(
        LEGACY_SCOPE,
        "Legacy v1 compatibility",
        "Frozen access to routes admitted at the v1 scope cutover.",
        "Legacy",
    ),
)

from .scope_registry_reads import read_scope_vocabulary
from .scope_registry_booking_reads import ARRIVAL_READ, BOOKING_READ, booking_read_catalog
_CATALOG += tuple(ScopeGrantOption(value, label, description, "Staff integration (operator-only)")
    for value, label, description in (
        ("events:read", "Event read", "Read minimal events through tenant-bound signed server routes."),
        ("participants:read", "Participants read", "Read participant IDs, display names and registration dates; requires events:read."),
        ("participants:attendance:read", "Attendance read", "Include attendance dates; requires events:read and participants:read."),
    ) if value in read_scope_vocabulary())
_CATALOG += tuple(ScopeGrantOption(value, label, description, "Staff integration (operator-only)")
                  for value, label, description in booking_read_catalog())


def validate_grantable_scopes(scopes, *, privileged):
    """Return a defensive list after applying the complete grant policy."""
    values = list(scopes or [])
    if not values:
        raise ValueError("At least one API-client scope is required.")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("API-client scopes cannot be empty.")
    if len(values) != len(set(values)):
        raise ValueError("Duplicate API-client scopes are not allowed.")
    unknown = sorted(set(values) - SCOPE_VOCABULARY)
    if unknown:
        raise ValueError(f"Unknown API-client scope(s): {', '.join(unknown)}.")
    requirements = {
        ARRIVAL_READ: {BOOKING_READ},
        "participants:read": {"events:read"},
        "participants:attendance:read": {"events:read", "participants:read"},
    }
    for value, dependencies in requirements.items():
        if value in values and not dependencies.issubset(values):
            raise ValueError(f"{value} requires {', '.join(sorted(dependencies))}.")
    allowed = SCOPE_VOCABULARY if privileged else TENANT_GRANTABLE_SCOPES
    forbidden = sorted(set(values) - allowed)
    if forbidden:
        raise ValueError(f"Scope(s) cannot be granted here: {', '.join(forbidden)}.")
    return values


def actor_may_grant_privileged_scopes(actor, makerspace_id):
    is_superadmin = bool(
        actor
        and (
            actor.is_superuser
            or getattr(actor, "role", None) == User.Role.SUPERADMIN
        )
    )
    return bool(
        is_superadmin
        and (
            makerspace_id is None
            or int(makerspace_id) not in rbac.superadmin_hidden_makerspace_ids()
        )
    )


def scope_catalog(*, privileged):
    allowed = SCOPE_VOCABULARY if privileged else TENANT_GRANTABLE_SCOPES
    lock_reason = "Only a global superadmin may grant this scope."
    return [
        {
            "value": option.value,
            "label": option.label,
            "description": option.description,
            "group": option.group,
            "grantable": option.value in allowed,
            "lock_reason": None if option.value in allowed else lock_reason,
        }
        for option in _CATALOG
    ]


__all__ = [
    "SUPERADMIN_ONLY_SCOPES",
    "TENANT_GRANTABLE_SCOPES",
    "actor_may_grant_privileged_scopes",
    "scope_catalog",
    "validate_grantable_scopes",
]
