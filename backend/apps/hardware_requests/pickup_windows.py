"""Pickup windows for loan requests (inventory D1/D14, #77).

* `loans.reservations` -- the member says when they will collect (a window up to
  `reservation_max_days_ahead` days away). A reservation is quantity-per-product and is
  held from accept, as every accepted request is (the cheapest D14 option: no time-ranged
  availability math).
* `loans.pickup_windows` -- an accepted request that is not collected by its deadline
  EXPIRES through the workflow and its reservation goes back to available. The deadline
  is the end of the member's window, else accept + `pickup_window_hours` (0 = never).
"""

from datetime import timedelta

from django.utils import timezone

from apps.hardware_requests.models_loans import LoanReservationPolicy
from apps.hardware_requests.workflow_errors import RequestValidationError
from apps.makerspaces.platform import feature_enabled

RESERVATIONS = "loans.reservations"
PICKUP_WINDOWS = "loans.pickup_windows"


def validate_window(makerspace, pickup_from, pickup_until, *, now=None):
    if pickup_from is None and pickup_until is None:
        return None, None
    if not feature_enabled(makerspace, RESERVATIONS):
        raise RequestValidationError("Choosing a pickup time is not available here.")
    now = now or timezone.now()
    start = pickup_from or now
    policy = LoanReservationPolicy.for_makerspace(makerspace)
    if start < now - timedelta(minutes=5):
        raise RequestValidationError("The pickup window cannot start in the past.")
    if start > now + timedelta(days=policy.reservation_max_days_ahead):
        raise RequestValidationError(
            f"Pickups can be booked at most {policy.reservation_max_days_ahead} days ahead.")
    if pickup_until is not None and pickup_until <= start:
        raise RequestValidationError("The pickup window must end after it starts.")
    return pickup_from, pickup_until


def deadline_at_accept(request, *, now=None):
    """The expiry deadline set at accept, or the member's own window end, or None."""
    if not feature_enabled(request.makerspace, PICKUP_WINDOWS):
        return request.pickup_until
    if request.pickup_until is not None:
        return request.pickup_until
    hours = LoanReservationPolicy.for_makerspace(request.makerspace).pickup_window_hours
    if not hours:
        return None
    now = now or timezone.now()
    return max(now, request.pickup_from or now) + timedelta(hours=hours)
