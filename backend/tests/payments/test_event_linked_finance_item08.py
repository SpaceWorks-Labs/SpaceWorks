"""Decision 216 item 8: the linked event finance view -- each section from its own owner,
currencies never summed, each section hidden by its own module/capability/authority."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.bookings.models import BookableSpace
from apps.bookings.services_bookings import create_booking
from apps.events.models import EventRegistration
from apps.events.models_booking_decision import EventBookingDecision
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_registry import core_module_keys
from apps.makerspaces.platform import module_enabled
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.models import ManualSettlement, Payment
from apps.payments.models_event_budget import EventFinanceBudget
from apps.payments.reconciliation import mark_offline
from tests.events.collab_helpers import client_for
from tests.events.ticketing_helpers import account, open_event
from tests.fixed_roles.helpers import staff_account
from tests.machines.certification_helpers import _member
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db
FEATURES = ["charges.enabled", "charges.events", "charges.bookings", "finance.ledger", "events.venue_fees",
            "events.account_registration"]


def _space(slug, modules=("events", "bookings")):
    return Makerspace.objects.create(name=slug, slug=slug, enabled_modules=sorted(core_module_keys() | set(modules)),
                                     enabled_features=FEATURES)


def _set(space, *, modules=None, features=None):
    if modules is not None:
        space.enabled_modules = sorted(modules)
    if features is not None:
        space.enabled_features = sorted(features)
    space.save(update_fields=["enabled_modules", "enabled_features"])


def _url(space, event):
    return f"/api/v1/admin/makerspace/{space.pk}/finance/events/{event.pk}/linked"


def _get(user, space, event):
    return client_for(user).get(_url(space, event))


def _charge(space, event, n, amount, currency, status="pending", **extra):
    user = account(f"{space.slug}-payer-{n}")
    registration = EventRegistration.objects.create(event=event, member=user, name=f"P{n}",
                                                    email=f"p{n}-{space.slug}@example.test", phone="1",
                                                    status="registered")
    return Payment.objects.create(makerspace=space, member=user, created_by=user, subject_type="event_registration",
                                  subject_id=registration.pk, amount=amount, currency=currency, status=status, **extra)


def _linked_booking(space, event, manager, amount="40.00"):
    resource = BookableSpace.objects.create(makerspace=space, name="Hall",
                                            approval_mode=BookableSpace.ApprovalMode.INSTANT)
    booker, _ = _member(space, f"{space.slug}-booker")
    start = timezone.now() + timedelta(days=3)
    booking = create_booking(resource, member=booker, actor=booker, starts_at=start, ends_at=start + timedelta(hours=2))
    assert not Payment.objects.filter(subject_type="booking", subject_id=booking.pk).exists()
    Payment.objects.create(makerspace=space, member=booker, created_by=booker, subject_type="booking",
                           subject_id=booking.pk, amount=amount, currency="inr", status="pending")
    EventBookingDecision.objects.create(makerspace=space, event=event, booking=booking, creator=manager,
                                        operation_id=uuid4(), intent={"version": 1})
    return booking


def _by_currency(section):
    return {row["currency"]: row for row in section["currencies"]}


def test_registration_charges_keep_currencies_and_settlement_facts_separate():
    space = _space("lf-currency")
    event = open_event(space)
    manager = make_member("lf-currency-sm", space)
    _charge(space, event, 1, "10.00", "inr")
    offline = _charge(space, event, 2, "20.00", "inr")
    mark_offline(offline, manager, {"method": "cash", "reference": "slip-1", "received_at": timezone.now()})
    _charge(space, event, 3, "5.00", "usd", status="paid_online", provider="stripe")
    EventFinanceBudget.objects.create(makerspace=space, event=event, event_id_snapshot=event.pk, currency="inr",
                                      amount="100.00", set_by=manager)
    response = _get(manager, space, event)
    assert response.status_code == 200, response.content
    sections = response.json()["sections"]
    rows = _by_currency(sections["registration_charges"])
    assert list(rows) == ["inr", "usd"]
    assert rows["inr"]["charges"] == 2 and rows["inr"]["owed"] == "10.00"
    assert rows["inr"]["paid_offline"] == "20.00" and rows["inr"]["paid_online"] == "0.00"
    assert rows["inr"]["offline_receipts"] == 1 and rows["inr"]["offline_by_method"] == {"cash": "20.00"}
    assert rows["usd"]["paid_online"] == "5.00" and rows["usd"]["offline_receipts"] == 0
    assert ManualSettlement.objects.filter(payment=offline).count() == 1
    budget = _by_currency(sections["budget"])
    assert budget["inr"]["budget"] == "100.00"
    assert all(set(row) >= {"currency", "net"} for row in sections["budget"]["currencies"])
    assert len({row["currency"] for row in sections["budget"]["currencies"]}) == len(sections["budget"]["currencies"])


def test_booking_room_charge_is_booking_owned_and_counted_once():
    space = _space("lf-booking")
    event = open_event(space)
    manager = make_member("lf-booking-sm", space)
    _charge(space, event, 1, "10.00", "inr")
    booking = _linked_booking(space, event, manager)
    sections = _get(manager, space, event).json()["sections"]
    room = sections["booking_room_charge"]
    assert room["owner"] == "bookings" and room["label"] == "Booking-owned" and room["read_only"] is True
    assert room["state"] == "linked" and room["booking_ids"] == [booking.pk]
    assert _by_currency(room)["inr"]["owed"] == "40.00" and _by_currency(room)["inr"]["charges"] == 1
    # Counted once: the room charge is never folded into the event's own charges or budget.
    assert _by_currency(sections["registration_charges"])["inr"]["owed"] == "10.00"
    assert "venue_fee" not in sections  # the booking owns the venue; no event fee row exists
    for row in sections["budget"]["currencies"]:
        assert row["income"] != "40.00"


def test_each_section_needs_its_own_authority():
    space = _space("lf-perm")
    event = open_event(space)
    manager = make_member("lf-perm-sm", space)
    _charge(space, event, 1, "10.00", "inr")
    _linked_booking(space, event, manager)
    EventPayoutObligation.objects.create(makerspace=space, event=event, event_id_snapshot=event.pk,
                                         event_title_snapshot=event.title, source_uuid=uuid4(),
                                         source_decision_revision=1, currency="INR", approved_minor=500)
    events_only = staff_account(space, "lf-perm-events", "event_manager")
    both = staff_account(space, "lf-perm-both", "event_manager", "booking_manager")
    bookings_only = staff_account(space, "lf-perm-bookings", "booking_manager")
    nobody = staff_account(space, "lf-perm-inventory", "inventory_manager")

    narrow = _get(events_only, space, event).json()["sections"]
    assert {"registration_charges", "budget"} <= set(narrow)
    assert not {"booking_room_charge", "payouts", "reimbursements"} & set(narrow)
    assert "booking_room_charge" in _get(both, space, event).json()["sections"]
    assert _get(bookings_only, space, event).status_code == 404  # cannot see the event itself
    assert _get(nobody, space, event).status_code == 404
    full = _get(manager, space, event).json()["sections"]
    payout = _by_currency(full["payouts"])["inr"]
    assert payout["approved"] == "5.00" and payout["paid"] == "0.00" and payout["remaining"] == "5.00"
    assert full["payouts"]["settlement"] == "offline"


def test_sections_follow_their_module_and_capability():
    space = _space("lf-modules")
    event = open_event(space)
    manager = make_member("lf-modules-sm", space)
    _linked_booking(space, event, manager)
    sections = _get(manager, space, event).json()["sections"]
    assert {"booking_room_charge", "budget", "registration_charges"} <= set(sections)
    assert ("reimbursements" in sections) == module_enabled(space, "event_reimbursements")

    _set(space, modules=set(space.enabled_modules) - {"bookings"},
         features=set(FEATURES) - {"finance.ledger", "charges.events"})
    sections = _get(manager, space, event).json()["sections"]
    assert "booking_room_charge" not in sections
    assert "budget" not in sections
    assert "registration_charges" not in sections  # tracking off and nothing recorded

    _charge(space, event, 1, "10.00", "inr")  # a historic debt stays visible after tracking is off
    charges = _get(manager, space, event).json()["sections"]["registration_charges"]
    assert charges["tracking_enabled"] is False and _by_currency(charges)["inr"]["owed"] == "10.00"

    _set(space, modules=set(space.enabled_modules) | {"event_reimbursements"})
    sections = _get(manager, space, event).json()["sections"]
    if module_enabled(space, "event_reimbursements"):
        assert sections["reimbursements"]["currencies"] == []

    _set(space, modules=set(space.enabled_modules) - {"events"})
    assert _get(manager, space, event).status_code == 404


def test_cross_tenant_is_denied():
    space, other = _space("lf-home"), _space("lf-away")
    event, foreign_event = open_event(space), open_event(other)
    manager = make_member("lf-home-sm", space)
    outsider = make_member("lf-away-sm", other)
    _charge(space, event, 1, "10.00", "inr")
    assert _get(outsider, space, event).status_code in (403, 404)
    assert client_for(manager).get(_url(space, foreign_event)).status_code == 404
    assert client_for(manager).get(f"/api/v1/admin/makerspace/{other.pk}/finance/events/{event.pk}/linked"
                                   ).status_code in (403, 404)
