"""Which machine-service rows a staff actor's machine reach covers.

Lives in the machines app, not the staff API, because the workflow re-checks it under
lock (`service_workflow_actions.collect`) and must not import a view module to do so.
The staff list and action views build their querysets from the same two predicates, so
the read the actor saw and the write they make agree on one definition.
"""

from django.db.models import Q

from apps.accounts import rbac
from apps.machines import role_scope
from apps.machines.models import MachineServiceRequest


def machine_partition_q(actor, makerspace_id):
    """The machine partition, or ``None`` for unrestricted machine authority.

    Exemption is resolved with ``role_scope.manage_scope_for``, NOT by asking whether
    ``makerspaces_for_action`` returned ``rbac.ALL``. Those two disagree for exactly one
    actor and it is the dangerous one: a global superadmin who also holds an explicit
    machine-scoped membership in a **hard-hidden** space is reduced to that role's
    authority by design, yet still answers ``ALL`` at the action level -- so the ALL
    shortcut handed them every row in the space and the role's machine links did nothing.
    ``manage_scopes_for`` already gives the right answer for both shapes (EXEMPT when a
    superadmin has no membership there, the role's links when they do), and using it is
    what keeps this partition consistent with the dashboard and every other surface.

    ``None`` rather than an empty ``Q()`` is load-bearing. Django's ``Q._combine``
    short-circuits a falsy operand -- ``Q() | Q(status=COMPLETED)`` returns
    ``Q(status=COMPLETED)``, not "everything OR completed" -- so an empty ``Q`` used as
    the identity for ``filter`` becomes an *annihilator* the moment the direct-collect arm
    is OR'd onto it. That inverted the union for every actor whose machine scope is
    unrestricted (a superadmin resolves to ``rbac.ALL``): instead of widening their view
    it narrowed it to COMPLETED rows only, hiding the entire live queue. Callers must
    therefore branch on ``None`` instead of relying on OR/AND identities.
    """
    scope = role_scope.manage_scope_for(actor, makerspace_id)
    if scope is role_scope.EXEMPT:
        return None
    return role_scope.scope_q_for(
        scope,
        machine_id_paths=role_scope.SERVICE_REQUEST_MACHINE_PATHS,
        type_id_paths=role_scope.SERVICE_REQUEST_TYPE_PATHS,
    )


def collect_partition_q(actor, makerspace_id):
    """Machine partition plus the direct-collect COMPLETED arm, or ``None`` for all rows."""
    visible = machine_partition_q(actor, makerspace_id)
    if visible is None:
        # Unrestricted machine authority already covers every row in the tenant; the
        # direct-collect arm can only be a subset of it, so there is nothing to add.
        return None
    if role_scope.role_grants_directly(
        actor, makerspace_id, rbac.Action.COLLECT_SERVICE_REQUEST
    ) or role_scope.organization_grants_directly(
        actor, makerspace_id, rbac.Action.COLLECT_SERVICE_REQUEST
    ):
        visible |= Q(status=MachineServiceRequest.Status.COMPLETED)
    return visible


def may_collect(actor, service_request):
    """Whether ``actor`` may still collect this row: the action AND the partition."""
    makerspace_id = service_request.makerspace_id
    if not rbac.can(actor, rbac.Action.COLLECT_SERVICE_REQUEST, makerspace_id):
        return False
    partition = collect_partition_q(actor, makerspace_id)
    if partition is None:
        return True
    return MachineServiceRequest.objects.filter(
        pk=service_request.pk, makerspace_id=makerspace_id,
    ).filter(partition).exists()
