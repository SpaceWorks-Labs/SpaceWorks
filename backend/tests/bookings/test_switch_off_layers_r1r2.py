"""Decision 218 (R1/R2): switching a layer off removes it from admission, readiness and the overlay.

R1 -- a retained room outage no longer refuses, warns or shows once `bookings.room_maintenance` is off.
R2 -- a linked machine's repair window no longer applies once the space turns the machines module off.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.busy_overlay import busy_blocks
from apps.maintenance.repairs.models_service import RoomOutage
from tests.bookings.test_booking_admission_readiness import checks, machine_world, preview, under_repair
from tests.maintenance.l16_helpers import switch

pytestmark = pytest.mark.django_db


def _window():
    now = timezone.now()
    return now, now + timedelta(days=2)


def test_room_outage_refuses_while_room_maintenance_is_on_and_vanishes_when_off():
    w = machine_world("r1-outage")
    RoomOutage.objects.create(makerspace=w.space, room=w.room, mode="block", reason="Flooded")
    assert checks(preview(w, space=w.room).json())["room_outage"]["state"] == "blocked"
    assert busy_blocks(w.room, *_window(), staff=True, closures=False)

    switch(w.space, off=("bookings.room_maintenance", "bookings.room_repairs"))
    data = preview(w, space=w.room).json()
    assert "room_outage" not in checks(data) and data["ready"] is True
    assert busy_blocks(w.room, *_window(), staff=True, closures=False) == []
    assert RoomOutage.objects.filter(room=w.room).exists()  # the record is retained, only the layer is off


def test_machine_repair_applies_only_while_the_machines_module_is_on():
    w = machine_world("r2-repair")
    under_repair(w)
    assert checks(preview(w).json())["machine_repair"]["state"] == "blocked"

    w.space.enabled_modules = sorted(set(w.space.enabled_modules) - {"machines", "machine_service"})
    w.space.save(update_fields=["enabled_modules"])
    w.time.refresh_from_db()
    # Decision 230d: with Machines off the machine's time cannot be booked, so the room shows one whole-window
    # "machine time off" block -- never the repair window itself (that carries the repair's own start).
    assert all(block["since"] is None for block in busy_blocks(w.time, *_window(), staff=True, closures=False))
    response = preview(w, member=False)
    if response.status_code == 200:  # the booking console still serves the room while machines are off
        assert "machine_repair" not in checks(response.json())
