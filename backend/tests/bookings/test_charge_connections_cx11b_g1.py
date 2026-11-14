"""Booking-owned charge seams: money tracking, pricing and optional rails are independent."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace, Booking
from apps.payments.models import Payment
from apps.payments.services import create_payment
from tests.bookings import admin_routes_cx11b_g1 as admin, member_routes_cx11b_g1 as member
from tests.bookings import organization_routes_cx11b_g1 as organization
from tests.bookings.route_support_cx11b_g1 import response_pair, send, world
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import domain_rows, switch
from tests.payments.pricing.helpers import rate

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings]
CREATORS = (
    (admin, "admin-space-booking-list"), (admin, "admin-recurring-bookings"),
    (admin, "admin-booking-approve"), (member, "public-booking-submit"),
    (organization, "admin-space-organization-booking"),
)
KEYS = ("charges.enabled", "charges.bookings", "charges.pricing", "payments", "payments.enabled", "payments.bookings")


def prepare(family, name, native, monkeypatch):
    route = next(row for row in family.ROUTES if row.name == name and row.method == "POST")
    w = world(route, native)
    family.setup(w, monkeypatch)
    BookableSpace.objects.filter(pk=w.room.pk).update(payment_amount="12.00")
    rate(w.tenant, "bookings", per_booking="0.00", per_hour="7.00")
    # Isolate the required ledger seam from the separately tested document worker.
    w.tenant.enabled_features.remove("billing.documents")
    w.tenant.save(update_fields=["enabled_features"])
    old_subject = w.booking
    if name == "admin-booking-approve":
        old_subject = Booking.objects.create(space=w.room, member=w.member, name="Retained historical charge",
            email=w.member.email, starts_at=w.start, ends_at=w.booking.ends_at, status="cancelled")
    old = create_payment(makerspace=w.tenant, subject_type="booking", subject_id=old_subject.pk,
        member=w.member, amount=Decimal("5.00"), currency="usd", created_by=w.actor)
    w.old_id = old.pk
    w.old_payment = Payment.objects.filter(pk=old.pk).values().get()
    w.url = reverse(name, kwargs=w.kwargs)
    return w


def admitted(w, amount):
    before_payments = set(Payment.objects.values_list("pk", flat=True))
    before_bookings = set(Booking.objects.values_list("pk", flat=True))
    before_audits = set(AuditLog.objects.values_list("pk", flat=True))
    response = send(w, w.client)
    assert response_pair(response) == (w.route.status, None), getattr(response, "data", None)
    name = w.route.name
    if name == "admin-booking-approve":
        ids = [w.booking.pk]
    elif name == "admin-recurring-bookings":
        ids = [x["booking_id"] for x in response.data["occurrences"]]
        assert len(ids) == 2 and len(set(ids)) == 2
    elif name == "public-booking-submit":
        ids = [Booking.objects.get(public_token=response.data["public_token"]).pk]
    else:
        ids = [response.data["id"]]
    assert list(Booking.objects.filter(pk__in=ids).order_by("pk").values_list("space_id", "member_id", "status")) == [
        (w.room.pk, w.member.pk, "confirmed")] * len(ids)
    created = set(Booking.objects.values_list("pk", flat=True)) - before_bookings
    assert created == (set() if name == "admin-booking-approve" else set(ids))
    payments = list(Payment.objects.exclude(pk__in=before_payments).order_by("subject_id"))
    if amount is None:
        assert payments == []
    else:
        assert [(p.subject_id, p.amount, p.currency, p.provider, p.status, p.member_id) for p in payments] == [
            (pk, amount, "usd", "unclaimed", "pending", w.member.pk) for pk in sorted(ids)]
        assert [Decimal(p.pricing_snapshot["total"]) for p in payments] == [amount] * len(ids)
        assert [p.pricing_snapshot["domain"] for p in payments] == ["bookings"] * len(ids)
    actions = ["booking.created"]
    if name == "admin-booking-approve":
        actions = ["booking.approved"] + (["booking.price_quoted_at_approval"] if amount is not None else [])
    elif name == "admin-space-organization-booking":
        actions = ["booking.organization_linked", "booking.created"]
    if amount is not None:
        actions += ["payment.created"]
    if name == "admin-recurring-bookings":
        actions = actions * 2 + ["booking.recurrence_created"]
    assert list(AuditLog.objects.exclude(pk__in=before_audits).order_by("pk").values_list("action", flat=True)) == actions
    assert Payment.objects.filter(pk=w.old_id).values().get() == w.old_payment


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("family,name", CREATORS, ids=[name for _, name in CREATORS])
def test_booking_charge_seam_retains_debt_and_restores_each_independent_policy(family, name, key, native, monkeypatch):
    w = prepare(family, name, native, monkeypatch)
    with rolled_back():
        admitted(w, Decimal("19.00"))
    before = domain_rows()
    original = switch(w.tenant, key)
    with rolled_back():
        amount = None if key in {"charges.enabled", "charges.bookings"} else Decimal("12.00") if key == "charges.pricing" else Decimal("19.00")
        admitted(w, amount)
    assert domain_rows() == before
    assert Payment.objects.filter(pk=w.old_id).values().get() == w.old_payment
    switch(w.tenant, key, original=original)
    admitted(w, Decimal("19.00"))
    written = domain_rows()
    switch(w.tenant, key)
    assert domain_rows() == written
    switch(w.tenant, key, original=original)
    assert domain_rows() == written
