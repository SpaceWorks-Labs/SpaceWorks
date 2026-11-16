"""Per-machine-type safety defaults for adapter bindings (decision 311a).

A binding inherits the profile of its machine's type and may override any key in its own config
(``services_adapter_safety.config_of``). Reading or editing a profile needs MANAGE_DEVICES in the space AND authority
over the TYPE (``machines.access.can_create_machine``, the per-type settings rule): a role scoped to some machines must
not relax the safety defaults of a type it does not manage (decision 336i). Edits are audited.
"""
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.audit import services as audit
from apps.devices.adapter_access import authorize_staff
from apps.devices.models import AdapterTypeProfile
from apps.devices.services_locks import lock_tenant


def _type(makerspace_id, machine_type_id):
    from apps.machines.models import MachineType
    machine_type = MachineType.objects.filter(pk=machine_type_id, makerspace_id=makerspace_id).first()
    if machine_type is None:
        raise NotFound()
    return machine_type


def _covers(actor, makerspace_id, machine_type):
    from apps.machines.access import can_create_machine
    return can_create_machine(actor, makerspace_id, machine_type)


def get_profile(actor, makerspace_id, machine_type_id):
    authorize_staff(actor, makerspace_id)
    machine_type = _type(makerspace_id, machine_type_id)
    if not _covers(actor, makerspace_id, machine_type):
        raise NotFound()  # per-type settings reads: a type outside the reader's links is absent
    row = AdapterTypeProfile.objects.filter(makerspace_id=makerspace_id, machine_type=machine_type).first()
    return {"machine_type_id": machine_type.pk, "config": row.config if row else {},
            "updated_at": row.updated_at if row else None}


def set_profile(actor, makerspace_id, machine_type_id, config):
    authorize_staff(actor, makerspace_id)
    machine_type = _type(makerspace_id, machine_type_id)
    if not _covers(actor, makerspace_id, machine_type):
        raise PermissionDenied(gettext("Machine type is outside your management scope."))
    with transaction.atomic():
        makerspace = lock_tenant(makerspace_id)
        row, _created = AdapterTypeProfile.objects.update_or_create(
            makerspace=makerspace, machine_type=machine_type,
            defaults={"config": config, "updated_by": actor, "updated_at": timezone.now()})
        audit.record(actor, "devices.adapter_profile_set", makerspace=makerspace, target=machine_type, meta={
            "machine_type_id": machine_type.pk, "config": config})
    return {"machine_type_id": machine_type.pk, "config": row.config, "updated_at": row.updated_at}
