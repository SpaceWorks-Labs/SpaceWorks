"""Credit a received grams To-Buy back to the machine consumable that raised it (MI-40)."""

from django.utils.translation import gettext
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit import services as audit
from apps.procurement import access
from apps.procurement.models import ToBuyItem


def _amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({"amount": gettext("Enter a valid quantity.")}) from None
    if not amount.is_finite() or amount <= 0:
        raise ValidationError({"amount": gettext("Amount must be greater than zero.")})
    return amount


@transaction.atomic
def refill_consumable(actor, item, amount):
    """Add ``amount`` grams to the origin consumable, exactly once per received item.

    Needs both authorities: the procurement stream (who owns the purchase) and machine
    `manage` (who owns the ledger). ``moved_to_inventory_at`` is the idempotency marker.
    """
    from apps.machines import access as machine_access
    from apps.machines.models import MachineConsumable
    locked = ToBuyItem.objects.select_for_update().select_related("makerspace").get(pk=item.pk)
    if locked.source_consumable_id is None:
        raise ValidationError({"detail": gettext("This item was not raised by a machine consumable.")})
    if locked.status != ToBuyItem.Status.RECEIVED:
        raise ValidationError({"status": gettext("Item must be received before it can refill its consumable.")})
    if locked.moved_to_inventory_at is not None:
        raise ValidationError({"detail": gettext("This item has already been credited.")})
    if not access.can_manage_kind(actor, locked.makerspace_id, locked.kind):
        raise PermissionDenied()
    row = MachineConsumable.objects.select_for_update(of=("self",)).select_related("machine").get(
        pk=locked.source_consumable_id)
    if row.machine.makerspace_id != locked.makerspace_id or row.measurement != MachineConsumable.Measurement.GRAMS:
        raise ValidationError({"detail": gettext("The source consumable cannot be refilled.")})
    if not row.machine.is_active:
        raise ValidationError({"detail": gettext("Machine is retired.")})
    if not machine_access.can_manage_machine(actor, row.machine):
        raise PermissionDenied()
    amount = _amount(amount)
    row.remaining += amount
    row.save(update_fields=["remaining"])
    locked.moved_to_inventory_at = timezone.now()
    locked.save(update_fields=["moved_to_inventory_at", "updated_at"])
    audit.record(actor, "procurement.consumable_refilled", makerspace=locked.makerspace, target=locked,
                 meta={"item_id": locked.pk, "consumable_id": row.pk, "amount": str(amount),
                       "remaining": str(row.remaining)})
    return row


def has_unresolved_item(consumable):
    """True while an open or received-but-uncredited item still targets ``consumable``."""
    return ToBuyItem.objects.filter(
        source_consumable=consumable, moved_to_inventory_at__isnull=True,
        status__in=[ToBuyItem.Status.REQUESTED, ToBuyItem.Status.APPROVED,
                    ToBuyItem.Status.ORDERED, ToBuyItem.Status.RECEIVED],
    ).exists()
