"""Edit and delete for ticket types and event categories, refusing changes history depends on.

A registration freezes its quote, but its `ticket_type` link is what reports, badges and the
check-in list read back. Deleting a used ticket type would silently null that link (SET_NULL)
and rewrite who bought what, so a referenced type can only be deactivated. Its price and
audience are likewise frozen once anybody registered with it. A category used by events is
refused for the same reason: SET_NULL would quietly uncategorise them.
"""

from django.utils.translation import gettext
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.audit.services import record
from apps.makerspaces.guards import require_module_locked

from .feature_gates import require_feature
from .capacity import CONFIRMED_STATUSES
from .models import EventCategory, EventRegistration, EventTicketType

TICKET_FIELDS = ("name", "amount", "audience", "capacity", "sales_start_at", "sales_end_at", "is_active",
                 "tier_group", "tier_rank", "pricing_mode", "min_amount", "seats_per_ticket", "is_hidden",
                 "min_quantity", "per_order_limit")
FROZEN_WHEN_USED = ("amount", "audience", "pricing_mode", "seats_per_ticket")


class ReferencedConflict(APIException):
    status_code = 409
    default_code = "referenced"

    def __init__(self, detail, code):
        super().__init__({"detail": detail, "code": code})


def _locked_ticket(ticket):
    from .services import _locked_event  # lock order: event -> makerspace
    event = _locked_event(ticket.event_id)
    event.makerspace = require_module_locked(event.makerspace, "events")
    require_feature(event, "events.ticket_types")
    return event, EventTicketType.objects.select_for_update().get(pk=ticket.pk, event=event)


@transaction.atomic
def update_ticket(ticket, *, actor, **values):
    from .services import _validate
    event, row = _locked_ticket(ticket)
    used = EventRegistration.objects.filter(ticket_type=row)
    from .models import EventOrderLine
    sold = used.exists() or EventOrderLine.objects.filter(ticket_type=row).exists()
    changed = sorted(field for field in TICKET_FIELDS if field in values and values[field] != getattr(row, field))
    if any(field in changed for field in FROZEN_WHEN_USED) and sold and not _price_drop(event, row, changed, values):
        raise ReferencedConflict(gettext("Price and audience are fixed once people registered with this ticket. "
                                 "Deactivate it and create a new ticket type instead."), "ticket_type_referenced")
    capacity = values.get("capacity", row.capacity)
    if "capacity" in changed and capacity and capacity < used.filter(status__in=CONFIRMED_STATUSES).count():
        raise ValidationError({"capacity": gettext("Capacity cannot be lower than the registered and attended seats on this ticket.")})
    for field in changed:
        setattr(row, field, values[field])
    _validate(row)
    if row.sales_start_at and row.sales_end_at and row.sales_end_at <= row.sales_start_at:
        raise ValidationError({"sales_end_at": gettext("Sales end must be after sales start.")})
    if changed:
        row.save(update_fields=changed)
        record(actor, "event.ticket_updated", makerspace=event.makerspace, target=row, meta={"fields": changed})
    if "amount" in changed:
        from apps.payments.price_drop.triggers import after_ticket_price
        after_ticket_price(actor, event, row)
    return row


def _price_drop(event, row, changed, values):
    """Lane L24 (#163A): with price-drop refunds on, a sold fixed-price ticket may get CHEAPER.

    Everything else stays frozen once sold; a rise is still refused, so nobody already
    holding the ticket can be asked for more, and the cheaper price opens refund cases.
    """
    from apps.makerspaces.platform import feature_enabled
    from apps.payments.price_drop import FEATURE
    frozen = [field for field in changed if field in FROZEN_WHEN_USED]
    return (frozen == ["amount"] and row.pricing_mode == "fixed" and values["amount"] < row.amount
            and feature_enabled(event.makerspace, FEATURE))


@transaction.atomic
def delete_ticket(ticket, *, actor):
    event, row = _locked_ticket(ticket)
    from .models import EventOrderLine
    if (EventRegistration.objects.filter(ticket_type=row).exists()
            or EventOrderLine.objects.filter(ticket_type=row).exists()):
        raise ReferencedConflict(gettext("Registrations or orders use this ticket type. Deactivate it instead of deleting it."),
                                 "ticket_type_referenced")
    record(actor, "event.ticket_deleted", makerspace=event.makerspace, target=row)
    row.delete()


def _locked_category(category):
    space = require_module_locked(category.makerspace_id, "events")
    return space, EventCategory.objects.select_for_update().get(pk=category.pk, makerspace=space)


@transaction.atomic
def update_category(category, *, actor, **values):
    space, row = _locked_category(category)
    changed = sorted(field for field in ("name", "slug") if field in values and values[field] != getattr(row, field))
    if "slug" in changed and EventCategory.objects.filter(makerspace=space, slug=values["slug"]).exclude(pk=row.pk).exists():
        raise ValidationError({"slug": gettext("Category already exists.")})
    for field in changed:
        setattr(row, field, values[field])
    if changed:
        row.save(update_fields=changed)
        record(actor, "event.category_updated", makerspace=space, target=row, meta={"fields": changed})
    return row


@transaction.atomic
def delete_category(category, *, actor):
    space, row = _locked_category(category)
    if row.events.exists():
        raise ReferencedConflict(gettext("Events use this category. Move them to another category first."),
                                 "category_referenced")
    record(actor, "event.category_deleted", makerspace=space, target=row)
    row.delete()
