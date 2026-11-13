"""Editing a machine type's consumable profile in one space (decision 341).

Authority is the per-type settings rule (`access.can_create_machine`): the Space Manager, or a
Machine Manager whose role scope covers the WHOLE type. A row a job already used is never
deleted -- it is switched off -- so every recorded usage keeps its definition.
"""

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace

from .consumable_profiles import validate_stock_link
from .models import MachineConsumablePool, MachineType
from .models_consumable_profiles import MachineTypeConsumable
from .template_spec import validate_consumable

EDITABLE = ("name", "kind", "unit", "attributes", "required", "estimate_by", "record_by", "unit_price",
            "consumable_pool", "product", "position", "is_active")


def _drf(exc):
    return ValidationError(getattr(exc, "message_dict", None) or {"detail": exc.messages})


def space_and_type(actor, makerspace_id, type_id, *, write=False):
    """The space and a type usable there (global or its own); 404 outside the actor's reach."""
    from .access import can_create_machine, can_see_machines
    space = get_object_or_404(Makerspace, pk=makerspace_id)
    require_module(space, "machines")
    owned = rbac.scope_verified_tenant(MachineType.objects.all(), space) | MachineType.objects.filter(
        makerspace__isnull=True)
    machine_type = owned.filter(pk=type_id).first()
    if machine_type is None or not can_see_machines(actor, space.pk):
        raise NotFound()
    if not can_create_machine(actor, space.pk, machine_type):
        if write:
            raise PermissionDenied(gettext("Machine type is outside your management scope."))
        raise NotFound()
    return space, machine_type


def profile(space, machine_type, *, active_only=False):
    rows = MachineTypeConsumable.objects.filter(makerspace=space, machine_type=machine_type)
    return rows.filter(is_active=True) if active_only else rows


def _stock(space, data):
    pool, product = data.get("consumable_pool"), data.get("product")
    if pool is not None and pool.makerspace_id != space.pk:
        raise ValidationError({"consumable_pool": gettext("That stock pool is not in this makerspace.")})
    if product is not None and product.makerspace_id != space.pk:
        raise ValidationError({"product": gettext("That inventory item is not in this makerspace.")})
    if pool is not None and product is not None:
        raise ValidationError({"consumable_pool": gettext("Link a stock pool or an inventory item, not both.")})
    try:
        validate_stock_link(data["unit"], pool.unit if pool is not None else None, product is not None)
    except ModelValidationError as exc:
        raise _drf(exc) from exc


def _check(space, data):
    try:
        validate_consumable({key: data[key] for key in ("key", "name", "kind", "unit", "required", "estimate_by",
                                                        "record_by", "attributes") if key in data})
    except ModelValidationError as exc:
        raise _drf(exc) from exc
    _stock(space, data)


@transaction.atomic
def create(actor, space, machine_type, data, *, template_key=""):
    data = {"kind": "material", "attributes": {}, "required": False, "estimate_by": "none", "record_by": ["staff"],
            **data}
    _check(space, data)
    try:
        with transaction.atomic():
            row = MachineTypeConsumable.objects.create(
                makerspace=space, machine_type=machine_type, template_key=template_key,
                **{key: data[key] for key in ("key", *EDITABLE) if key in data})
    except IntegrityError as exc:
        raise ValidationError({"key": gettext("This machine type already has a consumable with that key.")}) from exc
    audit.record(actor, "machine_type_consumable.created", makerspace=space, target=machine_type,
                 meta={"key": row.key, "unit": row.unit, "kind": row.kind})
    return row


@transaction.atomic
def update(actor, row, data):
    merged = {key: getattr(row, key) for key in ("key", *EDITABLE)}
    merged.update({key: value for key, value in data.items() if key in EDITABLE})
    if "unit" in data and data["unit"] != row.unit and row.usage.exists():
        raise ValidationError({"unit": gettext("Jobs already used this consumable; add a new one for another unit.")})
    _check(row.makerspace, merged)
    changed = sorted(key for key in EDITABLE if key in data and getattr(row, key) != merged[key])
    for key in changed:
        setattr(row, key, merged[key])
    row.save()
    audit.record(actor, "machine_type_consumable.updated", makerspace=row.makerspace, target=row.machine_type,
                 meta={"key": row.key, "fields": changed})
    return row


@transaction.atomic
def remove(actor, row):
    """Delete an unused row; a used one is switched off so its job history keeps resolving."""
    space, machine_type, key = row.makerspace, row.machine_type, row.key
    if row.usage.exists():
        row.is_active = False
        row.save(update_fields=["is_active", "updated_at"])
        outcome = "deactivated"
    else:
        row.delete()
        outcome = "deleted"
    audit.record(actor, f"machine_type_consumable.{outcome}", makerspace=space, target=machine_type,
                 meta={"key": key})
    return outcome


def pools_for(space, machine_type):
    """Stock pools a profile row may link to: the space's pools for this type or any type."""
    from django.db.models import Q
    return MachineConsumablePool.objects.filter(makerspace=space, is_active=True).filter(
        Q(machine_type__isnull=True, machine__isnull=True) | Q(machine_type=machine_type)
        | Q(machine__machine_type=machine_type))
