"""Canonical policy for deciding whether a makerspace may serve traffic.

A space the superadmin PAUSED (``LifecycleState.SUSPENDED``, #185) is unservable for
everyone except an active platform superadmin (#110/#190: nothing is hidden from the
superadmin). That one admission lives here, so rbac, lookups and every servable query
inherit it: ``admit_superadmin`` marks the current request or job once its actor is
authenticated, ``request_scope`` resets it per request. Reads then work normally;
writes still pass the source gate, where the superadmin's write is admitted and audited
(``space_controls.superadmin_bypass``). Archived spaces stay unservable for everyone.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.db.models import Q, QuerySet

from apps.makerspaces.models import Makerspace

ACTIVE = Makerspace.LifecycleState.ACTIVE
SUSPENDED = Makerspace.LifecycleState.SUSPENDED
_superadmin_admitted = ContextVar("servability_superadmin_admitted", default=False)


@contextmanager
def request_scope():
    """One request or job: the admission never outlives it (set by ``admit_superadmin``)."""
    token = _superadmin_admitted.set(False)
    try:
        yield
    finally:
        _superadmin_admitted.reset(token)


def admit_superadmin(user):
    """Admit paused spaces for the rest of this scope when ``user`` is a live platform superadmin."""
    from apps.accounts.platform_authority import is_platform_superadmin

    if is_platform_superadmin(user):
        _superadmin_admitted.set(True)


def superadmin_admitted() -> bool:
    return _superadmin_admitted.get()


def servable_states():
    return (ACTIVE, SUSPENDED) if _superadmin_admitted.get() else (ACTIVE,)


def is_servable(makerspace: Makerspace, *, allow_archived: bool = False) -> bool:
    """Return whether traffic may use it, optionally for archived recovery only.

    ``allow_archived`` answers the capability/settlement question (webhooks settling
    money, module and feature capability). A space a superadmin SUSPENDED (#185) keeps
    its data and money exactly like an archived one, so it passes that path too. Normal
    traffic refuses it unless the actor is the admitted superadmin.
    """
    state = makerspace.lifecycle_state
    if allow_archived:
        return state in (ACTIVE, SUSPENDED)
    return state in servable_states() and makerspace.archived_at is None


def servable_queryset(queryset: QuerySet | None = None, *, relation: str = ""):
    """Apply the canonical policy to a makerspace queryset or related queryset."""
    queryset = queryset if queryset is not None else Makerspace.objects.all()
    return queryset.filter(servable_q(relation))


def servable_q(relation: str = "") -> Q:
    """Return the canonical policy as a composable relation-aware query predicate."""
    prefix = f"{relation}__" if relation else ""
    return Q(
        **{
            f"{prefix}archived_at__isnull": True,
            f"{prefix}lifecycle_state__in": servable_states(),
        }
    )


def unservable_makerspace_ids() -> set[int]:
    """Return IDs that every normal authorization scope must exclude."""
    return archived_or_inactive_makerspace_ids()


def archived_or_inactive_makerspace_ids() -> set[int]:
    """Archived or non-active makerspaces: the whole unservable set.

    Kept as its own name because accounts/rbac.py pins callers to it; it equals
    `unservable_makerspace_ids` now that no opaque, not-restored tenant exists. Paused
    spaces are in it except for the admitted superadmin.
    """
    return set(
        Makerspace.objects.exclude(
            archived_at__isnull=True,
            lifecycle_state__in=servable_states(),
        ).values_list("id", flat=True)
    )
