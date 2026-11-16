"""Typed leave remarks: staff and member check-out, append-only history, issues."""
from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.bookings.models import Booking, BookingDepartureEvent, BookingIssue

from .helpers import client_for, world

pytestmark = pytest.mark.django_db


def _started(slug, permission="check_in"):
    return world(slug, permission=permission, approval="instant", start_in=timedelta(minutes=10))


def _depart_url(w):
    return reverse("admin-booking-arrival-depart", kwargs={"pk": w.space.pk, "booking_id": w.booking.pk})


def test_staff_records_issue_with_required_remark_and_issue_opens():
    w = _started("p2d-a")
    staff = client_for(w.grantee)
    assert staff.post(_depart_url(w), {"outcome": "damaged"}, format="json").status_code == 400
    assert staff.post(_depart_url(w), {"outcome": "nope", "remark": "x"}, format="json").status_code == 400
    response = staff.post(_depart_url(w), {"outcome": "damaged", "remark": "Bench vice cracked"}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["departed_at"] and response.json()["can_depart"] is False
    event = BookingDepartureEvent.objects.get(booking=w.booking)
    assert (event.outcome, event.remark, event.source) == ("damaged", "Bench vice cracked", "staff")
    issue = BookingIssue.objects.get(booking=w.booking)
    assert issue.outcome == "damaged" and issue.resolved_at is None
    audit = AuditLog.objects.get(action="booking.departure_recorded", makerspace=w.tenant)
    assert audit.meta["issue_id"] == issue.pk and "remark" not in audit.meta
    assert staff.post(_depart_url(w), {"outcome": "all_good"}, format="json").status_code == 409


def test_member_checkout_all_good_needs_no_remark_and_opens_no_issue():
    w = _started("p2d-b")
    url = reverse("member-booking-checkout",
                  kwargs={"makerspace_slug": w.tenant.slug, "public_token": w.booking.public_token})
    response = client_for(w.member).post(url, {"outcome": "all_good"}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["departure_outcome"] == "all_good" and body["can_checkout"] is False
    assert not BookingIssue.objects.filter(booking=w.booking).exists()
    assert client_for(w.grantee).post(url, {"outcome": "all_good"}, format="json").status_code == 404


def test_checkout_window_and_status_rules():
    w = world("p2d-c", permission="check_in", approval="instant", start_in=timedelta(days=2))
    url = reverse("member-booking-checkout",
                  kwargs={"makerspace_slug": w.tenant.slug, "public_token": w.booking.public_token})
    assert client_for(w.member).post(url, {"outcome": "left_early", "remark": "Too early"},
                                     format="json").status_code == 409
    w2 = world("p2d-d", permission="check_in", approval="approve", start_in=timedelta(minutes=5))
    pending = reverse("member-booking-checkout",
                      kwargs={"makerspace_slug": w2.tenant.slug, "public_token": w2.booking.public_token})
    assert client_for(w2.member).post(pending, {"outcome": "all_good"}, format="json").status_code == 409


def test_departure_rows_are_append_only_in_postgres():
    w = _started("p2d-e")
    client_for(w.grantee).post(_depart_url(w), {"outcome": "issue", "remark": "Projector missing"}, format="json")
    event = BookingDepartureEvent.objects.get(booking=w.booking)
    with pytest.raises(RuntimeError):
        event.save()
    for sql in ("UPDATE bookings_bookingdepartureevent SET outcome = 'all_good' WHERE id = %s",
                "DELETE FROM bookings_bookingdepartureevent WHERE id = %s"):
        with pytest.raises(Exception), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, [event.pk])


def test_issue_list_and_resolve_scoped_to_reservation_authority():
    w = _started("p2d-f", permission="manage_reservations")
    client_for(w.grantee).post(_depart_url(w), {"outcome": "issue", "remark": "Door code wrong"}, format="json")
    url = reverse("admin-booking-issues", kwargs={"makerspace_id": w.tenant.pk})
    listing = client_for(w.manager).get(url).json()
    assert listing["open_count"] == 1 and listing["results"][0]["remark"] == "Door code wrong"
    issue_id = listing["results"][0]["id"]
    resolved = client_for(w.grantee).post(reverse("admin-booking-issue-resolve", kwargs={"pk": issue_id}),
                                          {"note": "Code reset"}, format="json")
    assert resolved.status_code == 200 and resolved.json()["resolved_at"]
    assert client_for(w.manager).get(url).json()["open_count"] == 0
    assert client_for(w.manager).get(url, {"status": "resolved"}).json()["count"] == 1
    assert client_for(w.member).get(url).status_code == 403
    rows = client_for(w.manager).get(reverse("admin-space-booking-list", kwargs={"pk": w.space.pk})).json()["results"]
    assert rows[0]["departures"][0]["remark"] == "Door code wrong" and rows[0]["open_issue_id"] is None
    assert Booking.objects.get(pk=w.booking.pk).departed_at is not None
