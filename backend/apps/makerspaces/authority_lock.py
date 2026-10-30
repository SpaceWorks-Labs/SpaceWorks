"""Re-check a staff actor's authority under row locks, inside the write's transaction.

A view authorizes with ordinary reads and a service then mutates. Without a second check
under lock, a role edit, a removed membership, a revoked organization grant or link or
an archive that commits in between still lets the write land with authority the actor no
longer holds.

The order is the one every membership and role writer already takes: the makerspace row
first, then the actor's membership, its roles and the organization rows parent-first (the
`role_authority` locks). Any revocation is then either committed before these locks, and
so visible to the predicate re-run after them, or blocked until this transaction commits.
Callers lock the object they mutate AFTER this, never before, so the tenant row stays the
first lock on every path that touches it.
"""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceRole, MembershipAdditionalRole
from apps.makerspaces.role_authority import _locked_actor_actions

ACCESS_CHANGED = "Your access changed while saving. Reload and try again."


def lock_actor_authority(actor, makerspace_id):
    """Take the tenant and authority locks; return the locked makerspace."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("lock_actor_authority must run inside transaction.atomic().")
    makerspace = Makerspace.objects.select_for_update(no_key=True).get(pk=makerspace_id)
    # Locks the membership, its assigned role and the organization rows; the computed
    # action set is discarded because the caller re-runs its own, richer predicate.
    _locked_actor_actions(actor, makerspace)
    role_ids = sorted(
        MembershipAdditionalRole.objects.filter(
            membership__user_id=actor.pk, membership__makerspace_id=makerspace_id,
        ).values_list("role_id", flat=True)
    )
    if role_ids:
        list(MakerspaceRole.objects.select_for_update().filter(pk__in=role_ids).order_by("pk"))
    return makerspace


def require_under_lock(actor, makerspace_id, allowed):
    """Lock authority, then refuse unless the actor is still live and ``allowed()`` holds.

    ``allowed`` is the same predicate the view used, re-evaluated on fresh reads. It may
    raise its own ``PermissionDenied``/validation error; a falsy return is a 403.
    """
    makerspace = lock_actor_authority(actor, makerspace_id)
    live = User.objects.filter(
        pk=actor.pk, is_active=True, access_status=User.AccessStatus.ACTIVE,
    ).exists()
    if not live or not allowed():
        raise PermissionDenied(ACCESS_CHANGED)
    return makerspace
