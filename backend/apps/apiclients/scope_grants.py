from dataclasses import dataclass

from apps.accounts.models import User
from apps.apiclients.scope_registry import (
    AREA_SCOPES,
    BROWSER_SCOPES,
    LEGACY_SCOPE,
    PUBLIC_ALL,
    PUBLIC_READ,
    PUBLIC_WRITE,
    SCOPE_VOCABULARY,
)
from apps.apiclients.scope_registry_areas import AREAS, PEER_SCOPES, area_scope


# Area scopes only narrow public:read / public:write, so a Space Manager may grant them.
TENANT_GRANTABLE_SCOPES = frozenset({PUBLIC_READ, PUBLIC_WRITE}) | AREA_SCOPES
CLIENT_TYPE_SCOPES = {"server": SCOPE_VOCABULARY, "browser": BROWSER_SCOPES, "peer": PEER_SCOPES & AREA_SCOPES}
PEER_SCOPE_ERROR = "A peer (another space) client may only read the public catalogue, events and stats."
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
        ("orders:read", "Ticket orders read", "Read ticket orders: totals, lines and seat counts; no buyer contacts."),
        ("applications:read", "Application counts read",
         "Read application counts per event, by status and review stage; never applicants or answers."),
    ) if value in read_scope_vocabulary())
_CATALOG += tuple(ScopeGrantOption(value, label, description, "Staff integration (operator-only)")
                  for value, label, description in booking_read_catalog())
_CATALOG += tuple(
    ScopeGrantOption(area_scope(area, access), f"{label} {access}",
                     f"{'Read' if access == 'read' else 'Submit to'}: {description[0].lower()}{description[1:]}",
                     "Public API by area")
    for area, (label, description) in AREAS.items() for access in ("read", "write")
    if area_scope(area, access) in AREA_SCOPES
)


def validate_grantable_scopes(scopes, *, privileged, client_type=None):
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
    if client_type == "peer" and not set(values) <= CLIENT_TYPE_SCOPES["peer"]:
        raise ValueError(PEER_SCOPE_ERROR)
    allowed = SCOPE_VOCABULARY if privileged else TENANT_GRANTABLE_SCOPES
    forbidden = sorted(set(values) - allowed)
    if forbidden:
        raise ValueError(f"Scope(s) cannot be granted here: {', '.join(forbidden)}.")
    return values


def actor_may_grant_privileged_scopes(actor):
    return bool(
        actor
        and (
            actor.is_superuser
            or getattr(actor, "role", None) == User.Role.SUPERADMIN
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
            "client_types": [kind for kind, scopes in CLIENT_TYPE_SCOPES.items() if option.value in scopes],
        }
        for option in _CATALOG
    ]


__all__ = [
    "CLIENT_TYPE_SCOPES",
    "PEER_SCOPE_ERROR",
    "SUPERADMIN_ONLY_SCOPES",
    "TENANT_GRANTABLE_SCOPES",
    "actor_may_grant_privileged_scopes",
    "scope_catalog",
    "validate_grantable_scopes",
]
