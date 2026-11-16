from datetime import timedelta
from types import SimpleNamespace
from django.utils import timezone
from django.urls import reverse
from tests.bookings.staff_grant_helpers import grant_fixture, client_for
from apps.bookings.services_bookings import create_booking
from apps.bookings.services_arrival import qr_value


def world(slug="booking-arrival"):
    tenant, manager, scanner, resource, grant, owner = grant_fixture("check_in", slug)
    tenant.enabled_features = sorted(set(tenant.enabled_features) | {"bookings.confirmations", "bookings.checkin"})
    tenant.save(update_fields=["enabled_features"])
    resource.approval_mode = "instant"
    resource.save(update_fields=["approval_mode"])
    start = timezone.now() + timedelta(days=2)
    booking = create_booking(resource, member=owner, actor=owner, starts_at=start, ends_at=start + timedelta(hours=1))
    return SimpleNamespace(tenant=tenant, manager=manager, scanner=scanner, resource=resource,
                          grant=grant, owner=owner, booking=booking, credential=qr_value(booking))


def clock(monkeypatch, now):
    monkeypatch.setattr(timezone, "now", lambda: now)


def url(w, action):
    if action in ("resolve", "confirm"):
        return reverse("admin-booking-arrival-" + action, kwargs={"pk": w.resource.pk})
    return reverse("admin-booking-arrival-reverse", kwargs={"pk": w.resource.pk, "booking_id": w.booking.pk})


def owner_url(w, name="confirmation"):
    return reverse("member-booking-" + name, kwargs={"makerspace_slug": w.tenant.slug, "public_token": w.booking.public_token})
