"""Machine-area audit rows narrowed to the reader's machine-type reach.

Opening the ``machines`` area (``MANAGE_MACHINES`` / ``MANAGE_PRINTING``) is not enough to
read a machine row: a Machine Manager linked to lasers must not read the 3D-printer jobs,
sessions, schedules or certifications of the same space (``machines/role_scope.py``). A
scope-EXEMPT reader (the Space Manager, a null-role legacy membership) keeps every row. A
narrowed reader keeps a row only when it provably belongs to a machine or type they reach:
its target is one of those machines, types or their dependent rows, or its metadata names
one (``machine_id`` / ``machine_type_id``). Anything else fails CLOSED to the Space Manager,
like a repair row without subject metadata.
"""

from django.db.models import CharField, Q
from django.db.models.functions import Cast


def _ids(rows):
    return rows.annotate(audit_target=Cast("pk", output_field=CharField())).values("audit_target")


def _target(model, rows):
    return Q(target_type=model._meta.label_lower, target_id__in=_ids(rows))


def _type_ids(actor, space, scope):
    """Types the reader manages: their links plus direct type-manager grants. A per-machine
    operator assignment reaches that machine only, never its whole type."""
    from apps.machines import role_scope
    from apps.machines.access_scoping import _managing_actions
    from apps.machines.models import MachineType
    ids = set(scope[0])
    direct = [action for action in _managing_actions() if role_scope.grants_directly(actor, space.pk, action)]
    if direct:
        ids |= set(MachineType.objects.filter(Q(makerspace__isnull=True) | Q(makerspace=space),
                                              managing_action__in=direct).values_list("pk", flat=True))
    return sorted(ids)


def machines_q(actor, space, base):
    """``base`` (the machines-area action filter) narrowed to ``actor``'s machine reach."""
    from apps.machines import role_scope
    scope = role_scope.manage_scope_for(actor, space.pk)
    if scope is role_scope.EXEMPT:
        return base
    from apps.machines.access import scope_machines_for_actor
    from apps.machines.models import (
        CertificationGrant,
        CertificationType,
        Machine,
        MachineConsumablePool,
        MachineDowntime,
        MachineServiceRequest,
        MachineSession,
        MachineType,
        MakerspaceMachineTypePolicy,
        MakerspaceMachineTypePricing,
    )
    from apps.maintenance.models import (
        MaintenanceLog,
        MaintenanceLogDocument,
        MaintenanceSchedule,
    )
    machine_ids = sorted(scope_machines_for_actor(actor, Machine.objects.filter(makerspace=space))
                         .values_list("pk", flat=True))
    type_ids = _type_ids(actor, space, scope)
    # The same lookup paths as `role_scope.scoped_service_requests`.
    jobs = MachineServiceRequest.objects.filter(makerspace=space).filter(
        Q(assigned_machine_id__in=machine_ids) | Q(bucket__machine_id__in=machine_ids)
        | Q(assigned_machine__machine_type_id__in=type_ids) | Q(bucket__machine__machine_type_id__in=type_ids)
        | Q(queue__machine_type_id__in=type_ids))
    allowed = (
        _target(Machine, Machine.objects.filter(pk__in=machine_ids))
        | _target(MachineType, MachineType.objects.filter(pk__in=type_ids))
        | _target(MachineServiceRequest, jobs)
        | _target(MachineSession, MachineSession.objects.filter(machine_id__in=machine_ids))
        | _target(MachineDowntime, MachineDowntime.objects.filter(machine_id__in=machine_ids))
        | _target(MachineConsumablePool, MachineConsumablePool.objects.filter(
            # Mirrors `scoped_pools`: a type-bound pool is that type's; only a pool bound to
            # neither a machine nor a type is shared (machines audit 0.12.0).
            Q(machine_id__in=machine_ids) | Q(machine_type_id__in=type_ids)
            | Q(machine__isnull=True, machine_type__isnull=True), makerspace=space))
        | _target(CertificationType, CertificationType.objects.filter(machine_type_id__in=type_ids))
        | _target(CertificationGrant, CertificationGrant.objects.filter(
            certification_type__machine_type_id__in=type_ids))
        | _target(MakerspaceMachineTypePolicy, MakerspaceMachineTypePolicy.objects.filter(
            makerspace=space, machine_type_id__in=type_ids))
        | _target(MakerspaceMachineTypePricing, MakerspaceMachineTypePricing.objects.filter(
            makerspace=space, machine_type_id__in=type_ids))
        | _target(MaintenanceSchedule, MaintenanceSchedule.objects.filter(machine_id__in=machine_ids))
        | _target(MaintenanceLog, MaintenanceLog.objects.filter(machine_id__in=machine_ids))
        | _target(MaintenanceLogDocument, MaintenanceLogDocument.objects.filter(log__machine_id__in=machine_ids))
        | Q(meta__machine_id__in=machine_ids)
        | Q(meta__machine_type_id__in=type_ids)
    )
    return base & allowed


def repair_machines_q(actor, space):
    """Untargeted repair rows of a machine the reader manages (their scope) or, as a Technician,
    covers by machine type. A row with no ``meta.machine_id`` fails CLOSED to the Space Manager."""
    from apps.machines.access import scope_machines_for_actor
    from apps.machines.models import Machine
    from apps.accounts import rbac
    from apps.maintenance.repairs.authority import contact_for
    machines = Machine.objects.filter(makerspace=space)
    reach = Q(pk__in=[])
    if rbac.can(actor, rbac.Action.MANAGE_MACHINES, space.pk):
        reach |= Q(pk__in=scope_machines_for_actor(actor, machines).values("pk"))
    contact = contact_for(actor, space.pk)
    if contact is not None:
        types = [row.machine_type_id for row in contact.coverage.all() if row.kind == "machine_type"]
        reach |= Q(machine_type_id__in=types)
    from apps.maintenance.repairs.authority import membership_reach
    link_types, link_machines = membership_reach(actor, space.pk)
    reach |= Q(machine_type_id__in=link_types) | Q(pk__in=link_machines)
    return Q(meta__machine_id__in=list(machines.filter(reach).values_list("pk", flat=True)))
