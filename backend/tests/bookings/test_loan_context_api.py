"""Booking context API tests, pending real PostgreSQL test admission."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.models_loan_context import BookingLoanContext
from tests.test_request_workflow import make_space, make_member, make_product, make_hardware_request, authenticated_client

pytestmark = pytest.mark.django_db


def test_booking_context_link_and_stale_generation_refusal():
    space = make_space("booking-context-proof")
    space.enabled_modules = list(set(space.enabled_modules or []) | {"bookings", "request_workflow"})
    space.enabled_features = list(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    actor = make_member("booking-context-manager", space)
    product = make_product(space)
    req = make_hardware_request(space, product)
    room = BookableSpace.objects.create(makerspace=space, name="Workshop")
    start = timezone.now() + timedelta(days=3)
    booking = Booking.objects.create(space=room, name="Member", email="member@example.test",
        starts_at=start, ends_at=start + timedelta(hours=1))
    api = authenticated_client(actor)
    url = f"/api/v1/admin/makerspace/{space.pk}/requests/{req.pk}/booking-context"
    empty = api.get(url)
    assert empty.status_code == 200 and not empty.data["active"]
    body = {"booking_id": booking.pk, "expected_generation": empty.data["generation"], "expected_revision": 0}
    linked = api.put(url, body, format="json")
    assert linked.status_code == 200 and linked.data["revision"] == 1
    assert BookingLoanContext.objects.get(request=req).booking_id == booking.pk
    bad = dict(body, expected_generation="1e7a1922-8240-4f70-80f5-f16e9b995201", expected_revision=1)
    assert api.put(url, bad, format="json").status_code == 409
    assert BookingLoanContext.objects.get(request=req).booking_id == booking.pk


def test_booking_moved_to_another_space_after_snapshot_is_not_found(monkeypatch):
    from rest_framework.exceptions import NotFound
    from apps.bookings import loan_context_services as services
    space = make_space("booking-context-moved")
    space.enabled_modules = list(set(space.enabled_modules or []) | {"bookings", "request_workflow"})
    space.enabled_features = list(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    actor = make_member("booking-context-moved-manager", space)
    req = make_hardware_request(space, make_product(space))
    room = BookableSpace.objects.create(makerspace=space, name="Workshop")
    other = BookableSpace.objects.create(makerspace=space, name="Annex")
    start = timezone.now() + timedelta(days=3)
    booking = Booking.objects.create(space=room, name="Member", email="member@example.test",
        starts_at=start, ends_at=start + timedelta(hours=1))
    real = services.assert_write_allowed

    def move_then_allow(makerspace_id):  # Runs after the unlocked snapshot, before the row locks.
        Booking.objects.filter(pk=booking.pk).update(space=other)
        return real(makerspace_id)

    monkeypatch.setattr(services, "assert_write_allowed", move_then_allow)
    with pytest.raises(NotFound):
        services.mutate(actor, req, {"booking_id": booking.pk})
    assert not BookingLoanContext.objects.filter(request=req).exists()
