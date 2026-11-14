"""Each booking admission caller honours machine-time and retained room-outage policy."""
from dataclasses import replace
from datetime import timedelta

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace
from apps.machines.models import Machine, MachineType
from apps.maintenance.repairs.models_service import RoomOutage
from tests.bookings import admin_routes_cx11b_g1 as admin, member_routes_cx11b_g1 as member
from tests.bookings import organization_routes_cx11b_g1 as organization
from tests.bookings.route_support_cx11b_g1 import prove, response_pair, send, success, world
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import domain_rows, no_domain_writes, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings]
CALLERS = (
    (admin, "admin-space-booking-list"), (admin, "admin-recurring-bookings"),
    (admin, "admin-booking-time-edit"), (admin, "admin-booking-restore"),
    (member, "member-booking-reschedule"), (member, "public-booking-submit"),
    (organization, "admin-space-organization-booking"),
)


def prepare(family, name, native, monkeypatch):
    route = next(row for row in family.ROUTES if row.name == name and row.method == "POST")
    w = world(route, native)
    family.setup(w, monkeypatch)
    return w


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("family,name", CALLERS, ids=[name for _, name in CALLERS])
def test_each_machine_time_admission_checks_module_and_capability_independently(family, name, native, monkeypatch):
    w = prepare(family, name, native, monkeypatch)
    kind = MachineType.objects.create(makerspace=w.tenant, name="G1 retained machine type", slug="g1-machine-admission")
    machine = Machine.objects.create(makerspace=w.tenant, machine_type=kind,
        name="G1 retained machine", open_to_all_members=True)
    BookableSpace.objects.filter(pk=w.room.pk).update(machine=machine, machine_type=kind, kind="machine")
    w.route = replace(w.route, keys=("machines", "machines.time_booking"))
    w.off["machines"] = (404, "feature_disabled")
    prove(w)


def outage_refusal(w):
    before = domain_rows()
    if w.route.name == "admin-recurring-bookings":
        # Recurrence returns per-occurrence conflicts and audits the aggregate attempt.
        with rolled_back():
            audit_ids = set(AuditLog.objects.values_list("pk", flat=True))
            response = send(w, w.client)
            assert response_pair(response) == (200, None)
            assert [(x["booking_id"], x["status"]) for x in response.data["occurrences"]] == [(None, "conflict"), (None, "conflict")]
            assert list(AuditLog.objects.exclude(pk__in=audit_ids).values_list("action", flat=True)) == ["booking.recurrence_created"]
    else:
        with no_domain_writes():
            response = send(w, w.client)
        assert response_pair(response) == (409, "booking_conflict"), getattr(response, "data", None)
    assert domain_rows() == before


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("family,name", CALLERS, ids=[name for _, name in CALLERS])
def test_each_admission_ignores_retained_outage_off_and_restores_blocking_on(family, name, native, monkeypatch):
    w = prepare(family, name, native, monkeypatch)
    w.url = reverse(name, kwargs=w.kwargs)
    outage = RoomOutage.objects.create(makerspace=w.tenant, room=w.room, mode="block", reason="G1 retained room repair",
        started_at=w.now - timedelta(days=1), expected_back_at=w.start + timedelta(days=15))
    outage_refusal(w)
    before = domain_rows()
    original = switch(w.tenant, "bookings.room_maintenance")
    with rolled_back():
        success(w)
    assert domain_rows() == before
    switch(w.tenant, "bookings.room_maintenance", original=original)
    outage_refusal(w)
    assert domain_rows() == before
    switch(w.tenant, "bookings.room_maintenance")
    success(w)
    written = domain_rows()
    switch(w.tenant, "bookings.room_maintenance", original=original)
    assert domain_rows() == written
    outage.refresh_from_db()
    assert (outage.mode, outage.reason, outage.room_id) == ("block", "G1 retained room repair", w.room.pk)
