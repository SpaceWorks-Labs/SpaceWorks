"""Requests queue across spaces, and reject/cancel reasons shown to the requester."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace
from apps.bookings.services_bookings import create_booking

from .helpers import client_for, world

pytestmark = pytest.mark.django_db


def test_queue_lists_pending_across_every_manageable_space_only():
    w = world("p2q-a")
    other = BookableSpace.objects.create(makerspace=w.tenant, name="Second room", approval_mode="approve")
    start = timezone.now() + timedelta(days=3)
    second = create_booking(other, member=w.member, actor=w.member, starts_at=start, ends_at=start + timedelta(hours=1))
    url = reverse("admin-makerspace-booking-queue", kwargs={"makerspace_id": w.tenant.pk})
    manager = client_for(w.manager).get(url)
    assert manager.status_code == 200, manager.content
    assert {row["id"] for row in manager.json()["results"]} == {w.booking.pk, second.pk}
    assert {row["space_name"] for row in manager.json()["results"]} == {w.space.name, "Second room"}
    # A resource grant narrows the queue to the granted space.
    granted = client_for(w.grantee).get(url).json()
    assert [row["id"] for row in granted["results"]] == [w.booking.pk]
    confirmed = client_for(w.manager).get(url, {"status": "confirmed"}).json()
    assert confirmed["count"] == 0
    assert client_for(w.member).get(url).status_code == 403


def test_reject_requires_reason_and_shows_it_to_the_requester():
    w = world("p2q-b")
    url = reverse("admin-booking-reject", kwargs={"pk": w.booking.pk})
    staff = client_for(w.manager)
    assert staff.post(url, {}, format="json").status_code == 400
    assert staff.post(url, {"reason": "   "}, format="json").status_code == 400
    assert staff.post(url, {"reason": "x", "extra": 1}, format="json").status_code == 400
    response = staff.post(url, {"reason": "The room is closed for maintenance."}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["decision_reason"] == "The room is closed for maintenance."
    audit = AuditLog.objects.get(action="booking.rejected", makerspace=w.tenant)
    assert audit.meta["reason"] == "The room is closed for maintenance."
    mine = client_for(w.member).get(reverse("member-booking-list", kwargs={"makerspace_slug": w.tenant.slug}))
    assert mine.json()["results"][0]["decision_reason"] == "The room is closed for maintenance."


def test_cancel_reason_is_optional():
    w = world("p2q-c", approval="instant")
    url = reverse("admin-booking-cancel", kwargs={"pk": w.booking.pk})
    response = client_for(w.manager).post(url, {"reason": "Double booked"}, format="json")
    assert response.status_code == 200 and response.json()["decision_reason"] == "Double booked"
    w2 = world("p2q-d", approval="instant")
    plain = client_for(w2.manager).post(reverse("admin-booking-cancel", kwargs={"pk": w2.booking.pk}), {}, format="json")
    assert plain.status_code == 200 and plain.json()["decision_reason"] == ""


def test_member_dashboard_notices_for_decisions():
    from apps.bookings.member_notices import booking_notices
    from apps.makerspaces.models import MakerspaceMembership
    w = world("p2q-e")
    client_for(w.manager).post(reverse("admin-booking-reject", kwargs={"pk": w.booking.pk}),
                               {"reason": "Fully booked"}, format="json")
    membership = MakerspaceMembership.objects.get(user=w.member, makerspace=w.tenant)
    notices = booking_notices(membership, timezone.now())
    assert notices[0]["event"] == "booking_rejected" and notices[0]["body"] == "Fully booked"
