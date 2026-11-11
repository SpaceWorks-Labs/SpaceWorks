"""Shared fixtures for lane L6 ticketing tests (local only)."""

from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.events.models import EventSalesSettings
from apps.events.ticketing import create_ticket
from apps.payments.models import Payment
from tests.events.collab_helpers import client_for
from tests.return_helpers import make_member as _make_space_manager
from tests.events.ticketing_helpers import account, event_space, open_event

L6_FEATURES = ["events.orders", "events.seat_holds", "events.addons", "events.series_passes", "events.transfers",
               "events.desk_collect", "events.refund_override", "events.venue_fees"]


def make_staff(space, username="staff"):
    """A Space Manager (one account per person: the role decides, never an account kind)."""
    return _make_space_manager(f"{username}-{space.slug}", space)


def l6_space(slug="orders", *, features=None, membership=False):
    space = event_space(slug, membership=membership)
    space.enabled_features = sorted(set(space.enabled_features) | set(L6_FEATURES if features is None else features))
    space.save(update_fields=["enabled_features"])
    return space


def verified(name, **kwargs):
    user = account(name, **kwargs)
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return user


def ticketed_event(space=None, *, amount=10, capacity=0, ticket_capacity=0, **ticket_values):
    space = space or l6_space()
    event = open_event(space, capacity=capacity)
    staff = make_staff(space)
    ticket = create_ticket(event, actor=staff, name="General", amount=Decimal(amount), capacity=ticket_capacity,
                           **ticket_values)
    return space, event, staff, ticket


def order_url(event, name="member-event-orders"):
    return reverse(name, kwargs={"makerspace_id": event.makerspace_id, "event_id": event.pk})


def place(user, event, tickets, **body):
    return client_for(user).post(order_url(event), {"tickets": tickets, **body}, format="json")


def quote(user, event, tickets, **body):
    return client_for(user).post(order_url(event, "member-event-order-quote"), {"tickets": tickets, **body},
                                 format="json")


def order_payment(order):
    return Payment.objects.filter(subject_type="event_order", subject_id=order.pk).first()


def settle_offline(payment, actor):
    from apps.payments.reconciliation import mark_offline
    return mark_offline(payment, actor, {"method": "cash", "reference": "", "received_at": timezone.now()})


def settings_for(event, **values):
    row, _ = EventSalesSettings.objects.get_or_create(event=event, defaults={"makerspace": event.makerspace})
    for key, value in values.items():
        setattr(row, key, value)
    row.save()
    return row


def later(hours=1):
    return timezone.now() + timedelta(hours=hours)
