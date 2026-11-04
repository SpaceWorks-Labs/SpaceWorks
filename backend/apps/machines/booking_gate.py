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
"""

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
        raise MachineBookingRefused("machine_booked", "Someone else has booked this machine for now.")
    if purpose == "session" and requires_booking(machine.machine_type):
        if person_id is None or not bookings.filter(member_id=person_id).exists():
            raise MachineBookingRefused("booking_required", "Book this machine before using it.")
    return None
