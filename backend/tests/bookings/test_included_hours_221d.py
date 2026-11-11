"""Decision 221(d): membership plans include booking hours per term, used before pricing.

Written, not run: the consolidation lane runs it with the isolated Docker stack.
"""

import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.rbac import Action
from apps.bookings import included_hours
from apps.bookings.included_hours_ledger import consume, member_balances, release, used_minutes
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.models_included_hours import IncludedHoursUsage
from apps.bookings.services_bookings import approve_booking, create_booking, reject_booking
from apps.bookings.services_transitions import cancel_booking
from apps.makerspaces.models import MakerspaceMembership, MembershipTerm
from apps.payments.models import Payment
from tests.bookings.test_staff_price_confirmation import booking_debts, create, preview
from tests.machines.certification_helpers import _manager, _member, _space
from tests.payments.pricing.helpers import plan, put_on_plan, rate

pytestmark = pytest.mark.django_db
D = Decimal


def world(slug, *, hours=3, machine_hours=0, approval="instant", modules=("bookings", "membership")):
    maker = _space(slug, modules=modules, certifications=False)
    maker.enabled_features = sorted(set(maker.enabled_features) | {"charges.enabled", "charges.bookings",
                                                                    "charges.pricing"})
    maker.save(update_fields=["enabled_features"])
    rate(maker, "bookings", per_hour="10.00")
    staff, _ = _manager(maker, slug + "-desk", actions=(Action.MANAGE_BOOKINGS,))
    member, _ = _member(maker, slug + "-member")
    pro = plan(maker)
    pro.included_booking_hours, pro.included_machine_hours = hours, machine_hours
    pro.save(update_fields=["included_booking_hours", "included_machine_hours"])
    term = put_on_plan(maker, member, pro)
    room = BookableSpace.objects.create(makerspace=maker, name="Room", approval_mode=approval)
    client = APIClient()
    client.force_authenticate(staff)
    return maker, staff, member, room, term, client


def slot(day=1, hours=2):
    start = (timezone.now() + timedelta(days=day)).replace(microsecond=0, second=0, minute=0)
    return start, start + timedelta(hours=hours)


def book(room, member, *, day=1, hours=2, actor=None):
    start, end = slot(day, hours)
    return create_booking(room, starts_at=start, ends_at=end, member=member, actor=actor or member)


def test_hours_are_consumed_before_pricing_and_leave_no_debt_when_fully_covered():
    maker, _, member, room, term, _ = world("ih-full")
    booking = book(room, member, hours=2)
    assert booking.status == Booking.Status.CONFIRMED
    assert not booking_debts(maker).exists()  # 2h <= 3h allowance: nothing owed
    row = IncludedHoursUsage.objects.get(booking=booking)
    assert (row.entry, row.minutes, row.term_id, row.kind) == ("consume", 120, term.pk, "booking")
    assert member_balances(maker, member)[0]["remaining_minutes"] == 60


def test_only_the_hours_beyond_the_allowance_are_charged():
    maker, _, member, room, _, _ = world("ih-partial", hours=1)
    booking = book(room, member, hours=2)
    debt = booking_debts(maker).get(subject_id=booking.pk)
    assert debt.amount == D("10.00")  # 1 included hour + 1 priced hour
    assert IncludedHoursUsage.objects.get(booking=booking).minutes == 60


def test_balance_never_goes_negative_across_bookings():
    maker, _, member, room, term, _ = world("ih-neg", hours=3)
    book(room, member, day=1, hours=2)
    second = book(room, member, day=2, hours=2)
    assert IncludedHoursUsage.objects.get(booking=second).minutes == 60
    assert booking_debts(maker).get(subject_id=second.pk).amount == D("10.00")
    third = book(room, member, day=3, hours=1)
    assert not IncludedHoursUsage.objects.filter(booking=third).exists()  # exhausted: fully priced
    assert booking_debts(maker).get(subject_id=third.pk).amount == D("10.00")
    assert used_minutes(term, "booking") == 180


def test_cancel_restores_hours_once_and_a_second_release_is_a_noop():
    maker, staff, member, room, term, _ = world("ih-cancel")
    booking = book(room, member, hours=2)
    cancel_booking(booking, actor=member, member_cancel=True)
    assert used_minutes(term, "booking") == 0
    live = IncludedHoursUsage.objects.filter(booking=booking, entry="reverse").count()
    assert live == 1
    assert release(booking, staff) is None
    assert IncludedHoursUsage.objects.filter(booking=booking, entry="reverse").count() == 1


def test_staff_cancel_and_reject_of_a_pending_booking_restore_hours():
    maker, staff, member, room, term, _ = world("ih-reject", approval="approve")
    pending = book(room, member, hours=2)
    assert pending.status == Booking.Status.PENDING
    assert used_minutes(term, "booking") == 120  # a pending request holds its hours
    reject_booking(pending, actor=staff, reason="no")
    assert used_minutes(term, "booking") == 0
    again = book(room, member, day=2, hours=1)
    approve_booking(again, actor=staff)
    assert used_minutes(term, "booking") == 60
    cancel_booking(again, actor=staff)
    assert used_minutes(term, "booking") == 0


def test_consume_is_idempotent_per_booking():
    maker, _, member, room, term, _ = world("ih-idem")
    booking = book(room, member, hours=2)
    assert consume(booking) is None
    assert IncludedHoursUsage.objects.filter(booking=booking, entry="consume").count() == 1


def test_a_new_term_is_a_fresh_allowance_and_booking_follows_the_term_dates():
    maker, _, member, room, first, _ = world("ih-term", hours=2)
    membership = MakerspaceMembership.objects.get(makerspace=maker, user=member)
    second = MembershipTerm.objects.create(membership=membership, plan=first.plan, starts_at=first.ends_at,
                                           ends_at=first.ends_at + timedelta(days=30))
    # The room only takes bookings 30 days ahead by default; day 35 needs a longer window.
    BookableSpace.objects.filter(pk=room.pk).update(max_booking_advance_days=90)
    room.refresh_from_db()
    book(room, member, day=1, hours=2)
    assert used_minutes(first, "booking") == 120
    late = book(room, member, day=35, hours=2)  # starts inside the second term
    row = IncludedHoursUsage.objects.get(booking=late)
    assert row.term_id == second.pk and row.minutes == 120
    assert not booking_debts(maker).filter(subject_id=late.pk).exists()


def test_two_plans_hours_are_separate_pools_for_machine_time():
    maker, _, member, room, _, _ = world("ih-pools", hours=5, machine_hours=0)
    machine = BookableSpace.objects.create(makerspace=maker, name="Laser", kind="machine",
                                           approval_mode="instant")
    booking = book(machine, member, hours=1)
    assert not IncludedHoursUsage.objects.filter(booking=booking).exists()  # no machine hours in the plan


def test_staff_preview_shows_applied_and_remaining_hours_and_the_digest_follows_the_balance():
    maker, _, member, room, _, client = world("ih-preview", hours=3)
    start, end = slot(1, 2)
    body = {"member_id": member.pk, "starts_at": start.isoformat(), "ends_at": end.isoformat()}
    shown = preview(client, room, body)
    info = shown.data["included_hours"]
    assert (info["applied_minutes"], info["remaining_minutes"], info["allowance_minutes"]) == (120, 60, 180)
    assert D(shown.data["quote"]["total"]) == D("0.00")
    book(room, member, day=5, hours=2)  # another booking moves the balance
    stale = create(client, room, {**body, "price_confirmation": shown.data["price_confirmation"]})
    assert stale.status_code == 409 and stale.data["code"] == "price_changed"
    assert stale.data["confirmation"]["included_hours"]["applied_minutes"] == 60
    fresh = preview(client, room, body)
    ok = create(client, room, {**body, "price_confirmation": fresh.data["price_confirmation"]})
    assert ok.status_code == 201
    assert D(booking_debts(maker).get(subject_id=ok.data["id"]).amount) == D("10.00")


def test_member_activity_endpoint_lists_remaining_hours():
    maker, _, member, room, _, _ = world("ih-member")
    book(room, member, hours=2)
    client = APIClient()
    client.force_authenticate(member)
    data = client.get(reverse("member-activity", kwargs={"makerspace_id": maker.pk})).data
    pool = data["included_hours"][0]
    assert (pool["kind"], pool["allowance_minutes"], pool["used_minutes"], pool["remaining_minutes"]) == (
        "booking", 180, 120, 60)


def test_inert_when_the_membership_module_is_off():
    maker, _, member, room, term, client = world("ih-off")
    maker.enabled_modules = sorted(set(maker.enabled_modules) - {"membership"})
    maker.save(update_fields=["enabled_modules"])
    start, end = slot(1, 2)
    shown = preview(client, room, {"member_id": member.pk, "starts_at": start.isoformat(),
                                   "ends_at": end.isoformat()})
    assert shown.data["included_hours"] is None
    assert D(shown.data["quote"]["total"]) == D("20.00")
    booking = book(room, member, hours=2)
    assert not IncludedHoursUsage.objects.filter(booking=booking).exists()
    assert booking_debts(maker).get(subject_id=booking.pk).amount == D("20.00")
    assert member_balances(maker, member) == []


def test_event_venue_exemption_needs_a_staff_replacement_of_an_event_linked_booking(monkeypatch):
    maker, staff, member, room, _, _ = world("ih-venue")
    original = book(room, member, hours=1)
    assert included_hours.event_venue_exempt(room, member, staff, None) is False
    assert included_hours.event_venue_exempt(room, member, member, original) is False  # booking for themselves
    assert included_hours.event_venue_exempt(room, member, staff, original) is False  # not event-linked
    from apps.events.models import EventBookingDecision

    class Linked:
        def filter(self, **_):
            return self

        def exists(self):
            return True

    monkeypatch.setattr(EventBookingDecision, "objects", Linked())
    monkeypatch.setattr(included_hours, "module_enabled", lambda *_: True)
    assert included_hours.event_venue_exempt(room, member, staff, original) is True


@pytest.mark.django_db(transaction=True)
def test_concurrent_bookings_cannot_overdraw_the_term():
    maker, _, member, room, term, _ = world("ih-race", hours=2)
    results, errors = [], []

    def worker(day):
        try:
            results.append(book(room, member, day=day, hours=2).pk)
        except Exception as exc:  # a loser may legitimately fail admission; none may overdraw
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(day,)) for day in (1, 2, 3)]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    assert 0 <= used_minutes(term, "booking") <= 120
    assert Payment.objects.filter(makerspace=maker).count() >= len(results) - 1
