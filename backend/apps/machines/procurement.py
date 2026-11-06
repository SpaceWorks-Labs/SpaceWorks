"""Kernel destinations for received printing procurement items."""

from django.utils.translation import gettext
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from apps.machines.models import Machine, MachineConsumablePool, MachineType
from apps.machines.printer_capabilities import PRINTER_SLUG
from apps.makerspaces import limits
from apps.makerspaces.guards import require_module_locked


def move_received_printing(makerspace, actor, *, target, data, machine_type=None, source_pool=None):
    if target == "printer":
        return _create_printer(makerspace, actor, data, machine_type)
    if target == "spool":
        return _create_pool(makerspace, actor, _origin_defaults(data, source_pool), machine_type,
                            source_pool=source_pool)
    raise ValidationError({"target": gettext("Use spool or printer.")})


def _create_printer(makerspace, actor, data, machine_type):
    name = str(data.get("name") or "").strip()
    model = str(data.get("model") or "").strip()
    if not name:
        raise ValidationError({"name": gettext("This field is required.")})
    if not model:
        raise ValidationError({"model": gettext("This field is required.")})
    printer_type = MachineType.objects.get(makerspace__isnull=True, slug=PRINTER_SLUG)
    if machine_type is not None and machine_type.pk != printer_type.pk:
        raise ValidationError(
            {"machine_type": gettext("This item cannot create a machine of another type.")}
        )
    status = {"maintenance": Machine.Status.MAINTENANCE, "offline": Machine.Status.OFFLINE}.get(data.get("status"), Machine.Status.IDLE)
    # A received printer is a new MACHINE, so it takes the same two gates every other
    # machine creator takes, inside the caller's transaction: the `machines` module under
    # the makerspace row lock (race-safe against an uninstall) and the machine quota.
    # `printing` alone was checked, and it does not require `machines`.
    makerspace = require_module_locked(makerspace, "machines")
    limits.check_quota(makerspace, "machines", adding=1)
    return Machine.objects.create(makerspace=makerspace, machine_type=printer_type, name=name, notes=str(data.get("notes") or ""), status=status, is_active=data.get("is_active", True), type_payload={"model": model}, created_by=actor)


def _origin_defaults(data, source_pool):
    """A restock of a low pool refills that pool's line (MI-40): the new spool keeps the
    origin's material, colour, brand and machine unless the receiver says otherwise."""
    if source_pool is None:
        return data
    printer = source_pool.machine_id if (
        source_pool.machine_id and source_pool.machine.machine_type.slug == PRINTER_SLUG) else None
    merged = {"material": source_pool.material, "color": source_pool.color,
              "brand": source_pool.brand, "printer": printer}
    merged.update({key: value for key, value in dict(data).items() if value not in (None, "")})
    return merged


def _create_pool(makerspace, actor, data, machine_type, *, source_pool=None):
    material = str(data.get("material") or "").strip()
    if not material:
        raise ValidationError({"material": gettext("This field is required.")})
    initial = data.get("initial_weight_grams")
    remaining = data.get("remaining_weight_grams", initial)
    if initial is None:
        raise ValidationError({"initial_weight_grams": gettext("This field is required.")})
    initial = Decimal(str(initial))
    if initial < 0:
        raise ValidationError({"initial_weight_grams": gettext("Must be zero or greater.")})
    if remaining is None:
        raise ValidationError({"remaining_weight_grams": gettext("Remaining weight cannot exceed initial weight.")})
    remaining = Decimal(str(remaining))
    if remaining < 0:
        raise ValidationError({"remaining_weight_grams": gettext("Must be zero or greater.")})
    if remaining > initial:
        raise ValidationError({"remaining_weight_grams": gettext("Remaining weight cannot exceed initial weight.")})
    machine = None
    if data.get("printer") is not None:
        machine = Machine.objects.filter(pk=data["printer"], makerspace=makerspace, machine_type__slug=PRINTER_SLUG).first()
        if machine is None:
            raise ValidationError({"printer": gettext("Printer must belong to the same makerspace.")})
        if machine_type is not None and machine.machine_type_id != machine_type.pk:
            raise ValidationError(
                {"machine_type": gettext("This item cannot create a pool for another machine type.")}
            )
    if machine is None and source_pool is not None and source_pool.machine_type_id:
        machine_type = source_pool.machine_type
    pool = MachineConsumablePool.objects.create(
        makerspace=makerspace,
        machine=machine,
        machine_type=machine_type if machine is None else None,
        material=material,
        color=str(data.get("color") or "").strip(),
        brand=str(data.get("brand") or "").strip(),
        lot_code=str(data.get("lot_code") or "").strip(),
        initial_grams=initial,
        remaining_grams=remaining,
        unit=source_pool.unit if source_pool is not None else MachineConsumablePool._meta.get_field("unit").default,
        color_hex=source_pool.color_hex if source_pool is not None else "",
        low_threshold_grams=(source_pool.low_threshold_grams if source_pool is not None else None)
        or makerspace.filament_low_stock_threshold_grams or None,
        is_active=data.get("is_active", True),
        opened_at=data.get("opened_at"),
        created_by=actor,
    )
    from apps.machines.low_stock import maybe_flag_low_stock
    maybe_flag_low_stock(actor, pool)
    return pool
