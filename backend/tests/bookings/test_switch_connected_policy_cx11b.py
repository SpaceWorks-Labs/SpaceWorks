"""CX11B: machine time and room outages are retained admission policies."""
from datetime import timedelta

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from apps.maintenance.repairs.models_service import RoomOutage
from tests.bookings.test_booking_admission_readiness import machine_world
from tests.maintenance.l16_helpers import tomorrow
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, domain_rows, switch

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("key,code", [("bookings", "module_disabled"), ("machines", "feature_disabled"),
                                      ("machines.time_booking", "feature_disabled")])
def test_machine_time_policy_preserves_an_existing_booking_and_restores_new_admission(native, key, code):
    w = machine_world("cx11b-machine-time")
    client = client_for(w.manager, w.space, native)
    start = tomorrow()[0]
    url = reverse("admin-space-booking-list", args=[w.time.pk])

    def send(at):
        return client.post(url, {"house": True, "starts_at": at.isoformat(),
            "ends_at": (at + timedelta(hours=1)).isoformat()}, format="json")

    created = send(start)
    assert response_pair(created) == (201, None), created.data
    row = Booking.objects.get(pk=created.data["id"])
    before = domain_rows()
    original = switch(w.space, key)
    with no_domain_writes():
        refused = send(start + timedelta(hours=2))
    assert response_pair(refused) == (404, code), refused.data
    assert domain_rows() == before
    switch(w.space, key, original=original)
    assert domain_rows() == before
    restored = send(start + timedelta(hours=2))
    assert response_pair(restored) == (201, None), restored.data
    row.refresh_from_db()
    assert (row.status, row.starts_at, row.is_house) == ("confirmed", start, True)
    assert AuditLog.objects.filter(action="booking.created", target_id=str(row.pk)).count() == 1
    assert Booking.objects.filter(space=w.time).count() == 2


@pytest.mark.parametrize("native", [False, True])
def test_retained_room_outage_is_ignored_off_and_blocks_admission_again_on(native):
    w = machine_world("cx11b-room-outage")
    outage = RoomOutage.objects.create(makerspace=w.space, room=w.room, mode="block", reason="Water ingress")
    client = client_for(w.manager, w.space, native)
    start = tomorrow()[0]
    url = reverse("admin-space-booking-list", args=[w.room.pk])
    body = {"house": True, "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat()}
    before = domain_rows()
    response = client.post(url, body, format="json")
    assert response_pair(response) == (409, "booking_conflict"), response.data
    assert domain_rows() == before
    original = switch(w.space, "bookings.room_maintenance")
    created = client.post(url, body, format="json")
    assert response_pair(created) == (201, None), created.data
    written = domain_rows()
    switch(w.space, "bookings.room_maintenance", original=original)
    assert domain_rows() == written
    outage.refresh_from_db()
    assert (outage.mode, outage.reason) == ("block", "Water ingress")
    body.update(starts_at=(start + timedelta(hours=2)).isoformat(), ends_at=(start + timedelta(hours=3)).isoformat())
    response = client.post(url, body, format="json")
    assert response_pair(response) == (409, "booking_conflict"), response.data
    assert domain_rows() == written
