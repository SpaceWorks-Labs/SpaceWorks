"""L16 (#93, C-6b, C-9, Q-T1 a): out of service, room outages and item/room maintenance."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.exceptions import BookingConflict
from apps.bookings.services_bookings import create_booking
from apps.inventory.models import InventoryAsset
from apps.maintenance.models import RoomOutage, SubjectMaintenanceLog, SubjectMaintenanceSchedule
from apps.maintenance.repairs import maintenance_subjects, service_state
from tests.machines.certification_helpers import _member
from tests.maintenance.l16_helpers import in_house, switch, tomorrow, world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def post_state(user, w, **body):
    return authenticated_client(user).post(f"/api/v1/admin/makerspaces/{w.space.pk}/service-state", body,
                                           format="json")


def test_a_covering_technician_takes_a_machine_out_of_service_and_back():
    w = world("l16-ss-machine")
    assert post_state(w.tech, w, subject_type="machine", subject_id=w.machine.pk,
                      in_service=False).json()["code"] == "out_of_scope"
    in_house(w, coverage=[{"kind": "machine_type", "machine_type": w.kind}])
    out = post_state(w.tech, w, subject_type="machine", subject_id=w.machine.pk, in_service=False,
                     reason="Belt snapped")
    assert out.status_code == 200 and out.json()["state"] == "maintenance"
    w.machine.refresh_from_db()
    assert w.machine.status == "maintenance"
    assert post_state(w.tech, w, subject_type="machine", subject_id=w.other.pk,
                      in_service=False).status_code == 403
    assert post_state(w.tech, w, subject_type="machine", subject_id=w.machine.pk,
                      in_service=True).json()["state"] == "idle"


def test_units_and_items_change_state_only_through_availability():
    w = world("l16-ss-items")
    asset = InventoryAsset.objects.create(makerspace=w.space, product=w.product, asset_tag="SI-1",
                                          status=InventoryAsset.Status.AVAILABLE)
    result = service_state.set_state(w.im, w.space, subject_type="inventory_asset", subject=asset,
                                     in_service=False)
    asset.refresh_from_db()
    assert result["state"] == "maintenance" and asset.status == "maintenance"
    service_state.set_state(w.manager, w.space, subject_type="inventory_product", subject=w.product,
                            in_service=False, quantity=2)
    w.product.refresh_from_db()
    assert w.product.needs_fix_quantity == 3  # the unit above plus two counted units


def test_a_room_outage_blocks_new_bookings_lists_the_affected_and_warn_mode_allows():
    w = world("l16-ss-room")
    member, _ = _member(w.space, "l16-ss-room-member")
    start, end = tomorrow()
    booked = create_booking(w.room, member=member, actor=member, starts_at=start, ends_at=end)
    out = post_state(w.manager, w, subject_type="bookable_space", subject_id=w.room.pk, in_service=False,
                     reason="Flooded")
    assert out.status_code == 200 and [row["id"] for row in out.json()["affected_bookings"]] == [booked.pk]
    with pytest.raises(BookingConflict):
        create_booking(w.room, member=member, actor=member, starts_at=start + timedelta(days=1),
                       ends_at=end + timedelta(days=1))
    assert post_state(w.manager, w, subject_type="bookable_space", subject_id=w.room.pk,
                      in_service=True).status_code == 200
    assert RoomOutage.objects.get(room=w.room).ended_at is not None
    post_state(w.manager, w, subject_type="bookable_space", subject_id=w.room.pk, in_service=False, mode="warn")
    create_booking(w.room, member=member, actor=member, starts_at=start + timedelta(days=2),
                   ends_at=end + timedelta(days=2))


def test_item_maintenance_schedules_run_by_a_covering_technician_and_switch_gated():
    w = world("l16-upkeep")
    schedule = maintenance_subjects.create_schedule(
        w.im, w.space, subject_type="inventory_product", subject=w.product, description="Clean tips",
        interval_days=7, next_due=timezone.localdate())
    tech = authenticated_client(w.tech)
    assert tech.post(f"/api/v1/admin/subject-maintenance/{schedule.pk}/run", {"summary": "Done"},
                     format="json").status_code == 403
    in_house(w, coverage=[{"kind": "inventory"}])
    ran = tech.post(f"/api/v1/admin/subject-maintenance/{schedule.pk}/run", {"summary": "Cleaned"}, format="json")
    assert ran.status_code == 201, ran.content
    schedule.refresh_from_db()
    assert schedule.next_due == timezone.localdate() + timedelta(days=7)
    assert SubjectMaintenanceLog.objects.filter(schedule=schedule, performed_by=w.tech).count() == 1
    mine = tech.get(f"/api/v1/admin/makerspaces/{w.space.pk}/my-maintenance").json()
    assert [row["id"] for row in mine["schedules"]] == [schedule.pk]
    switch(w.space, off=("inventory.maintenance", "inventory.repairs"))
    assert tech.post(f"/api/v1/admin/subject-maintenance/{schedule.pk}/run", {"summary": "x"},
                     format="json").status_code == 404
    assert SubjectMaintenanceSchedule.objects.filter(pk=schedule.pk).exists()


def test_a_covering_technician_completes_a_machine_schedule():
    from apps.maintenance.models import MaintenanceSchedule
    w = world("l16-upkeep-machine")
    row = MaintenanceSchedule.objects.create(machine=w.machine, description="Mirror clean", interval_days=30,
                                             next_due=timezone.localdate())
    in_house(w, coverage=[{"kind": "machine_type", "machine_type": w.kind}])
    tech = authenticated_client(w.tech)
    assert [item["id"] for item in tech.get(
        f"/api/v1/admin/makerspaces/{w.space.pk}/my-maintenance").json()["machine_schedules"]] == [row.pk]
    done = tech.post(f"/api/v1/admin/maintenance/schedules/{row.pk}/run", {"summary": "Cleaned"}, format="json")
    assert done.status_code == 201, done.content
    other = MaintenanceSchedule.objects.create(machine=w.other, description="Spindle", interval_days=30,
                                               next_due=timezone.localdate())
    assert tech.post(f"/api/v1/admin/maintenance/schedules/{other.pk}/run", {"summary": "x"},
                     format="json").status_code == 403


def test_a_covering_technician_never_edits_a_machine_schedule():
    from rest_framework.exceptions import PermissionDenied
    from apps.maintenance.models import MaintenanceSchedule
    from apps.maintenance.services_workflows import update_schedule
    w = world("l16-upkeep-edit")
    row = MaintenanceSchedule.objects.create(machine=w.machine, description="Mirror clean", interval_days=30,
                                             next_due=timezone.localdate())
    in_house(w, coverage=[{"kind": "machine_type", "machine_type": w.kind}])
    with pytest.raises(PermissionDenied):
        update_schedule(row, actor=w.tech, interval_days=7)
