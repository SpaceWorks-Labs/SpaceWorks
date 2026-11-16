"""Capacity math shared by volunteer places and office-hour team places."""
from django.utils.translation import gettext
from django.db import connection
from .errors import ProgrammeError


def remaining_locked(slot, *, booked):
    if not connection.in_atomic_block:
        raise RuntimeError("Allocation requires the locked slot parent.")
    return None if slot.capacity == 0 else max(0, slot.capacity - booked)


def require_place_locked(slot, *, booked):
    if remaining_locked(slot, booked=booked) == 0:
        code = "office_hours_full" if slot.kind == "office_hours" else "shift_full"
        raise ProgrammeError(code, gettext("This slot is full."))


def require_capacity_edit(slot, *, capacity, booked):
    if capacity and capacity < booked:
        raise ProgrammeError("active_bookings", gettext("Capacity cannot be below existing allocations."))
