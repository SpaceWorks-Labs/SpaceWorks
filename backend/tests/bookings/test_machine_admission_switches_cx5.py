"""Machine-time booking admission through HTTP: switches, repair bounds and tenant scope."""
from datetime import timedelta

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from apps.maintenance.repairs import service_state
from apps.payments.models import Payment, Refund, RefundCase
from tests.bookings.test_booking_admission_readiness import machine_world
from tests.maintenance.l16_helpers import tomorrow
from tests.return_helpers import authenticated_client
from tests.refusal_helpers_mod2b import refused

pytestmark = pytest.mark.django_db


def create(w, *, api=None, start=None):
    start = start or tomorrow()[0]
    return (api or authenticated_client(w.manager)).post(reverse("admin-space-booking-list", args=[w.time.pk]),
        {"house": True, "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat()}, format="json")


@pytest.mark.parametrize("key,code", [("bookings", "module_disabled"), ("machines", "feature_disabled"),
                                      ("machines.time_booking", "feature_disabled")])
def test_booking_and_machine_switches_refuse_then_restore_without_a_partial_booking(key, code):
    w = machine_world("cx5-booking-switch")
    field = "enabled_features" if "." in key else "enabled_modules"
    original = list(getattr(w.space, field))
    setattr(w.space, field, [value for value in original if value != key])
    w.space.save(update_fields=[field])
    refused(create(w), 404, code)
    assert not Booking.objects.filter(space=w.time).exists()
    assert not Payment.objects.filter(makerspace=w.space).exists()
    assert not AuditLog.objects.filter(makerspace=w.space, action="booking.created").exists()
    setattr(w.space, field, original)
    w.space.save(update_fields=[field])
    restored = create(w)
    assert restored.status_code == 201, restored.content
    assert restored.json()["status"] == "confirmed"
    assert Booking.objects.filter(space=w.time, status="confirmed", is_house=True).count() == 1
    assert AuditLog.objects.filter(makerspace=w.space, action="booking.created").count() == 1
    assert not Payment.objects.filter(makerspace=w.space).exists()


def test_repair_end_boundary_is_exclusive_and_does_not_cancel_existing_bookings():
    w = machine_world("cx5-booking-repair")
    back = tomorrow()[0]
    created = create(w, start=back - timedelta(hours=2))
    assert created.status_code == 201, created.content
    existing = Booking.objects.get(pk=created.json()["id"])
    assert existing.status == "confirmed"
    original = (existing.status, existing.starts_at, existing.ends_at, existing.member_id,
                existing.public_token, existing.pricing_snapshot, existing.replaces_id, existing.is_house,
                existing.cancelled_at, existing.status_before_cancel)
    payments = list(Payment.objects.filter(makerspace=w.space).order_by("pk").values())
    refunds = list(Refund.objects.filter(payment__makerspace=w.space).order_by("pk").values())
    cases = list(RefundCase.objects.filter(payment__makerspace=w.space).order_by("pk").values())

    def assert_existing_preserved():
        existing.refresh_from_db()
        assert (existing.status, existing.starts_at, existing.ends_at, existing.member_id,
                existing.public_token, existing.pricing_snapshot, existing.replaces_id, existing.is_house,
                existing.cancelled_at, existing.status_before_cancel) == original
        assert list(Payment.objects.filter(makerspace=w.space).order_by("pk").values()) == payments
        assert list(Refund.objects.filter(payment__makerspace=w.space).order_by("pk").values()) == refunds
        assert list(RefundCase.objects.filter(payment__makerspace=w.space).order_by("pk").values()) == cases
        assert not AuditLog.objects.filter(makerspace=w.space, action="booking.cancelled",
                                           target_type="bookings.booking", target_id=str(existing.pk)).exists()

    service_state.set_state(w.manager, w.space, subject_type="machine", subject=w.machine,
                            in_service=False, reason="Extractor repair", expected_back_at=back)
    assert_existing_preserved()
    refused(create(w, start=back - timedelta(minutes=1)), 409, "machine_under_repair")
    assert list(Booking.objects.filter(space=w.time).values_list("pk", flat=True)) == [existing.pk]
    assert_existing_preserved()
    at_boundary = create(w, start=back)
    assert at_boundary.status_code == 201, at_boundary.content
    booking = Booking.objects.get(pk=at_boundary.json()["id"])
    assert booking.starts_at == back and booking.status == "confirmed"
    assert_existing_preserved()
    assert AuditLog.objects.filter(makerspace=w.space, action="booking.created", target_id=str(booking.pk)).count() == 1


def test_foreign_tenant_cannot_book_a_known_machine_time_resource():
    w = machine_world("cx5-booking-tenant")
    foreign = machine_world("cx5-booking-tenant-other")
    refused(create(w, api=authenticated_client(foreign.manager)), 404, "not_found")
    assert not Booking.objects.filter(space=w.time).exists()
    assert not AuditLog.objects.filter(makerspace=w.space, action="booking.created").exists()
