"""Decision 216 item 4: staff see a booking's admission readiness before submit, read-only.

Local (tests are gitignored by convention). Repair, lockout, outage and certification are
reported from the admission seams themselves; the maintenance link is scope-checked.
"""
from datetime import timedelta
from unittest import mock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.rbac import Action
from apps.audit.models import AuditLog
from apps.bookings.admission_readiness import readiness
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.services_bookings import create_booking
from apps.maintenance.models import MaintenanceSchedule
from apps.maintenance.repairs import service_state
from apps.maintenance.repairs.models_service import RoomOutage
from tests.account_split_g2_helpers import staff_for_actions
from tests.machines.certification_helpers import _certification, _member
from tests.maintenance.l16_helpers import switch, tomorrow, world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def machine_world(slug):
    w = world(slug)
    switch(w.space, on=("machines.time_booking",))
    w.time = BookableSpace.objects.create(makerspace=w.space, name="Laser A time", machine=w.machine,
                                          machine_type=w.kind, approval_mode=BookableSpace.ApprovalMode.INSTANT)
    w.member, _ = _member(w.space, f"{slug}-member")
    return w


def checks(data):
    return {row["code"]: row for row in data["checks"]}


def preview(w, user=None, *, space=None, member=True):
    start, end = tomorrow()
    params = {"starts_at": start.isoformat(), "ends_at": end.isoformat()}
    if member:
        params["member_id"] = w.member.pk
    return authenticated_client(user or w.manager).get(
        reverse("admin-space-booking-readiness", kwargs={"pk": (space or w.time).pk}), params)


def under_repair(w):
    service_state.set_state(w.manager, w.space, subject_type="machine", subject=w.machine, in_service=False)
    w.machine.refresh_from_db()


def lock_out(w):
    MaintenanceSchedule.objects.create(machine=w.machine, description="Extractor filter", interval_days=30,
                                       next_due=timezone.localdate() - timedelta(days=2), blocks_use=True)


@__import__("pytest").mark.skip(reason="Decision 319: certification gating retired (machine access grants replace it); see tests/parity_0120/machine_access.")
def test_a_healthy_machine_reads_ready_with_every_applicable_check_ok():
    w = machine_world("ready-ok")
    response = preview(w)
    assert response.status_code == 200, response.content
    assert response["Cache-Control"] == "private, no-store"
    rows = checks(response.json())
    assert set(rows) == {"room_outage", "machine_repair", "machine_lockout", "certification"}
    assert all(row["state"] == "ok" for row in rows.values())
    assert response.json()["ready"] is True and response.json()["maintenance_link"] is None


def test_repair_blocks_and_offers_the_machine_maintenance_link_to_its_manager():
    w = machine_world("ready-repair")
    under_repair(w)
    data = preview(w).json()
    assert checks(data)["machine_repair"]["state"] == "blocked"
    assert data["ready"] is False
    assert data["maintenance_link"] == {"machine_id": w.machine.pk}


def test_lockout_is_advisory_and_still_offers_the_link():
    w = machine_world("ready-lockout")
    lock_out(w)
    data = preview(w).json()
    assert checks(data)["machine_lockout"]["state"] == "warning"
    assert data["ready"] is True  # admission does not refuse a booking on lockout
    assert data["maintenance_link"] == {"machine_id": w.machine.pk}


@__import__("pytest").mark.skip(reason="Decision 319: certification gating retired (machine access grants replace it); see tests/parity_0120/machine_access.")
@pytest.mark.parametrize("mode,state", [("block", "blocked"), ("warn", "warning")])
def test_room_outage_is_reported_from_the_admission_seam(mode, state):
    w = machine_world("ready-outage-" + mode)
    RoomOutage.objects.create(makerspace=w.space, room=w.room, mode=mode, reason="Flooded")
    data = preview(w, space=w.room).json()
    assert checks(data)["room_outage"]["state"] == state
    assert "machine_repair" not in checks(data) and data["maintenance_link"] is None
    assert data["ready"] is (state != "blocked")


@__import__("pytest").mark.skip(reason="Decision 319: certification gating retired (machine access grants replace it); the machine_access check is covered in tests/parity_0120/machine_access.")
def test_missing_certification_blocks_and_names_it_then_clears_without_a_member():
    w = machine_world("ready-cert")
    switch(w.space, on=("machines.certifications",))
    _certification(w.space, w.kind, name="Laser induction")
    row = checks(preview(w).json())["certification"]
    assert row["state"] == "blocked" and row["certifications"] == ["Laser induction"]
    assert "certification" not in checks(preview(w, member=False).json())


def test_readiness_writes_nothing():
    w = machine_world("ready-nowrite")
    switch(w.space, on=("machines.certifications",))
    _certification(w.space, w.kind)
    under_repair(w)
    lock_out(w)
    before = (Booking.objects.count(), AuditLog.objects.count())
    start, end = tomorrow()
    with CaptureQueriesContext(connection) as queries:
        readiness(w.time, member=w.member, starts_at=start, ends_at=end, actor=w.manager)
    writes = [q["sql"] for q in queries.captured_queries
              if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
    assert writes == []
    assert preview(w).status_code == 200
    assert (Booking.objects.count(), AuditLog.objects.count()) == before


def test_maintenance_feature_off_hides_lockout_and_link_but_repair_still_blocks():
    w = machine_world("ready-feature-off")
    under_repair(w)
    lock_out(w)
    switch(w.space, off=("machines.maintenance", "machines.repairs"))
    data = preview(w).json()
    assert checks(data)["machine_repair"]["state"] == "blocked"
    assert "machine_lockout" not in checks(data)
    assert data["maintenance_link"] is None


def test_maintenance_app_inactive_skips_outage_and_link():
    w = machine_world("ready-app-off")
    under_repair(w)
    RoomOutage.objects.create(makerspace=w.space, room=w.time, mode="block")
    inactive = lambda label: label != "maintenance"  # noqa: E731
    # The outage layer asks `admission.room_outages_apply`, which reads the registry directly.
    with mock.patch("apps.bookings.admission_readiness.runtime_active", inactive), mock.patch("apps.separability.registry.runtime_active", inactive):
        data = readiness(w.time, member=None, starts_at=tomorrow()[0], ends_at=tomorrow()[1], actor=w.manager)
    assert "room_outage" not in checks(data) and data["maintenance_link"] is None


def test_bookings_module_off_refuses_the_preview():
    w = machine_world("ready-bookings-off")
    w.space.enabled_modules = [m for m in w.space.enabled_modules if m != "bookings"]
    w.space.save(update_fields=["enabled_modules"])
    assert preview(w).status_code in (400, 403, 404)


def test_wrong_type_machine_manager_gets_no_link_right_type_does():
    w = machine_world("ready-scope")
    under_repair(w)
    start, end = tomorrow()
    wrong, _ = staff_for_actions(w.space, "ready-scope-cnc", [Action.MANAGE_MACHINES], machine_types=[w.other_kind])
    right, _ = staff_for_actions(w.space, "ready-scope-laser", [Action.MANAGE_MACHINES], machine_types=[w.kind])
    assert readiness(w.time, member=None, starts_at=start, ends_at=end, actor=wrong)["maintenance_link"] is None
    assert readiness(w.time, member=None, starts_at=start, ends_at=end,
                     actor=right)["maintenance_link"] == {"machine_id": w.machine.pk}
    # Through the API: a Booking Manager + CNC-scoped Machine Manager sees the repair, not the link.
    desk, _ = staff_for_actions(w.space, "ready-scope-desk", [Action.MANAGE_MACHINES, Action.MANAGE_BOOKINGS],
                                machine_types=[w.other_kind])
    data = preview(w, desk).json()
    assert checks(data)["machine_repair"]["state"] == "blocked" and data["maintenance_link"] is None


def test_staff_without_reservation_rights_are_refused():
    w = machine_world("ready-denied")
    outsider, _ = staff_for_actions(w.space, "ready-denied-cnc", [Action.MANAGE_MACHINES], machine_types=[w.kind])
    assert preview(w, outsider).status_code in (403, 404)


def test_cross_tenant_staff_cannot_preview():
    w = machine_world("ready-tenant")
    other = machine_world("ready-tenant-b")
    assert preview(w, other.manager).status_code in (403, 404)


def test_existing_booking_readiness_reflects_a_later_repair():
    w = machine_world("ready-existing")
    start, end = tomorrow()
    booking = create_booking(w.time, member=w.member, actor=w.member, starts_at=start, ends_at=end)
    under_repair(w)
    response = authenticated_client(w.manager).get(reverse("admin-booking-readiness", kwargs={"pk": booking.pk}))
    assert response.status_code == 200, response.content
    assert checks(response.json())["machine_repair"]["state"] == "blocked"
    assert response.json()["maintenance_link"] == {"machine_id": w.machine.pk}
    other = machine_world("ready-existing-b")
    denied = authenticated_client(other.manager).get(reverse("admin-booking-readiness", kwargs={"pk": booking.pk}))
    assert denied.status_code in (403, 404)
