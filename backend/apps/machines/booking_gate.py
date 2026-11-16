"""The `requires_booking` gate (MI-43, machines D1): who may use a machine right now.

Reusable on purpose: machine-service `start` calls it today, and machine sessions (L23,
#158) call it at session start. Machine time is booked through `bookings`: a bookable
resource linked to the machine (`BookableSpace.machine`, `machines.time_booking`).

* `purpose="session"` -- a person operating the machine themself. When the machine's type
  `requires_booking`, they must hold a live booking on it now (`booking_required`).
* `purpose="service"` -- staff running a member's job. Nobody else may hold the machine
  now (`machine_booked`); the job's own member holding it is fine.
* Either way, a live booking by someone else refuses (`machine_booked`).

Inert when `machines.time_booking` or the `bookings` app is off: nothing can be booked,
so nothing is enforced -- exactly release 1's behaviour.

A machine out of service for repair (`status == "maintenance"`, set by repairs'
`service_state`) refuses NEW bookings of its time that overlap the repair window
(`refuse_if_under_repair`, called from bookings admission), and the bookings already inside
it are listed to staff (`bookings_in_repair`), as a blocking room outage does.
"""

from django.utils.translation import gettext
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

LIVE = ("confirmed",)
FEATURE = "machines.time_booking"


class MachineBookingRefused(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "machine_booked"

    def __init__(self, code, detail):
        super().__init__({"detail": detail, "code": code}, code)
        self.code = code


def requires_booking(machine_type):
    return bool((machine_type.capability_config or {}).get("requires_booking"))


def live_bookings(machine, at=None):
    """Confirmed bookings on this machine's time covering `at` (empty when not bookable)."""
    from apps.makerspaces.platform import feature_enabled
    from apps.separability.registry import runtime_active
    if not runtime_active("bookings") or not feature_enabled(machine.makerspace, FEATURE):
        return None
    from apps.bookings.models import Booking
    at = at or timezone.now()
    return Booking.objects.filter(space__machine_id=machine.pk, space__is_active=True, status__in=LIVE,
                                  starts_at__lte=at, ends_at__gt=at)


def check(machine, person, *, purpose, at=None):
    """Raise `MachineBookingRefused` unless `person` may use `machine` now for `purpose`."""
    bookings = live_bookings(machine, at)
    if bookings is None:
        return None
    person_id = getattr(person, "pk", person)
    if bookings.exclude(member_id=person_id).exists():
        raise MachineBookingRefused("machine_booked", gettext("Someone else has booked this machine for now."))
    if purpose == "session" and requires_booking(machine.machine_type):
        if person_id is None or not bookings.filter(member_id=person_id).exists():
            raise MachineBookingRefused("booking_required", gettext("Book this machine before using it."))
    return None


UNDER_REPAIR = "maintenance"


def repair_window(machine):
    """``(started_at, expected_back_at)`` while the machine is under repair, else None.

    Either bound is None when unknown (no open downtime row: `machines.maintenance` off).
    """
    if machine.status != UNDER_REPAIR:
        return None
    from .models import MachineDowntime
    row = MachineDowntime.objects.filter(machine=machine, ended_at__isnull=True).first()
    return (row.started_at, row.expected_back_at) if row else (None, None)


def refuse_if_under_repair(machine, starts_at, ends_at):
    """The bookings admission seam: a machine under repair refuses an overlapping new booking."""
    window = repair_window(machine)
    if window is None:
        return
    started, back = window
    if (started is None or ends_at > started) and (back is None or starts_at < back):
        from apps.bookings.exceptions import MachineUnderRepair
        raise MachineUnderRepair()


def bookings_in_repair(machine, expected_back_at=None, *, now=None):
    """Pending or confirmed bookings of this machine's time from now until it is expected back."""
    from apps.separability.registry import runtime_active
    if not runtime_active("bookings"):
        return []
    from apps.bookings.models import Booking
    rows = Booking.objects.filter(space__machine_id=machine.pk, status__in=("pending", "confirmed"),
                                  ends_at__gt=now or timezone.now())
    if expected_back_at is not None:
        rows = rows.filter(starts_at__lt=expected_back_at)
    return list(rows.order_by("starts_at", "id"))
