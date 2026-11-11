"""Per-makerspace monthly quotas the superadmin sets on ANY space (owner 2026-11-11).

Keys: ``events_monthly``, ``bookings_monthly``, ``payments_monthly_count``, ``payments_monthly_amount``
(whole currency units, checked per currency). They live in ``Makerspace.resource_limit_overrides``,
apply to every space (own or hosted, plans on or off) and default to NO limit: absent / null / -1.

What a quota may and may not do (docs/INVARIANTS.md, "Quotas never block settling"):

* It refuses only the START of something new: a new event, a new booking, a new paid ticket, booking,
  shop order, plan purchase or donation (typed 409).
* It never touches existing events or bookings, never blocks paying an existing charge (online on any
  rail, or offline), refunds, or recording a debt in the ledger (``payments.create_payment`` is not gated).
"""
from datetime import UTC, datetime

from django.utils.translation import gettext
from rest_framework.exceptions import APIException

SPACE_QUOTA_KEYS = frozenset({"events_monthly", "bookings_monthly", "payments_monthly_count",
                              "payments_monthly_amount"})
LABELS = {
    "events_monthly": "events created this month",
    "bookings_monthly": "bookings created this month",
    "payments_monthly_count": "paid transactions this month",
    "payments_monthly_amount": "money taken this month (per currency)",
}
CODES = {"events_monthly": "event_quota_reached", "bookings_monthly": "booking_quota_reached",
         "payments_monthly_count": "payment_quota_reached", "payments_monthly_amount": "payment_quota_reached"}


class SpaceQuotaReached(APIException):
    status_code = 409
    default_code = "quota_reached"

    def __init__(self, key, limit, makerspace=None):
        message = gettext("This space has reached its monthly allowance of %(what)s (%(limit)s). "
                          "Ask the platform operator to raise it.") % {"what": gettext(LABELS[key]), "limit": limit}
        super().__init__({"detail": message, "code": CODES[key], "limit": limit})
        self.code = CODES[key]
        self.key, self.makerspace_id = key, getattr(makerspace, "pk", None)


def tell_managers(exc):
    """Once a month per quota, tell the Space Managers and superadmins that this quota stopped something.

    Called by the API exception handler AFTER the refusing transaction has rolled back (the check runs inside
    the creator's ``transaction.atomic()``, so a write made at the raise point would be rolled back with it).
    The inbox row's key is deterministic, so repeats the same month change nothing. Never raises."""
    try:
        from apps.makerspaces.models import Makerspace

        from .limit_notices import notify_reached
        space = Makerspace.objects.filter(pk=exc.makerspace_id).first()
        if space is not None:
            notify_reached(space, exc.key, month_start().strftime("%Y-%m"), LABELS[exc.key], quota=True)
    except Exception:
        return None


def quota_limit(makerspace, key):
    """The superadmin's limit (int) or None = no limit (the default)."""
    overrides = makerspace.resource_limit_overrides or {}
    if key not in overrides:
        from .enforcement import NOT_SET, plan_limit  # a hosted space's plan answers when no override is set (#261)
        planned = plan_limit(makerspace, key)
        return None if planned is NOT_SET else planned
    value = overrides[key]
    if value is None or isinstance(value, bool) or value == -1:
        return None
    return int(value)


def month_start():
    now = datetime.now(UTC)
    return datetime(now.year, now.month, 1, tzinfo=UTC)


def quota_used(makerspace, key, currency=None):
    """Usage this month. Cancelled bookings and events still count (churn must not reset the quota)."""
    start = month_start()
    if key == "events_monthly":
        from apps.events.models import Event
        return Event.objects.filter(makerspace=makerspace, created_at__gte=start).count()
    if key == "bookings_monthly":
        from apps.bookings.models import Booking
        return Booking.objects.filter(space__makerspace=makerspace, created_at__gte=start).count()
    from django.db.models import Sum

    from apps.payments.models import Payment
    rows = Payment.objects.filter(makerspace=makerspace, created_at__gte=start).exclude(
        status=Payment.Status.CANCELED)
    if key == "payments_monthly_count":
        return rows.count()
    if currency:
        rows = rows.filter(currency=currency.lower())
    return int(rows.aggregate(t=Sum("amount"))["t"] or 0)


def check_space_quota(makerspace, key, *, adding=1, currency=None):
    """Raise the typed 409 when ``adding`` more would pass the limit; a no-op while unlimited."""
    limit = quota_limit(makerspace, key)
    if limit is None:
        return
    if quota_used(makerspace, key, currency) + adding > limit:
        raise SpaceQuotaReached(key, limit, makerspace=makerspace)


def require_payment_capacity(makerspace, amount, currency):
    """Gate the START of a new paid transaction (ticket, booking, shop order, plan purchase, donation)."""
    from .availability import plans_enabled
    if makerspace is None or not ((makerspace.resource_limit_overrides or {}) or plans_enabled()):
        return
    check_space_quota(makerspace, "payments_monthly_count")
    check_space_quota(makerspace, "payments_monthly_amount", adding=int(-(-amount // 1)) if amount else 0,
                      currency=currency)


def usage_rows(makerspace):
    """Read-only rows for the Space Manager / area managers and the superadmin console."""
    from apps.makerspaces.limit_registry import area_of

    from .usage import level
    rows = []
    for key in sorted(SPACE_QUOTA_KEYS):
        limit = quota_limit(makerspace, key)
        try:
            used = quota_used(makerspace, key)
        except Exception:
            used = None
        percent = round(used * 100 / limit, 1) if limit and used is not None else (100.0 if limit == 0 else None)
        rows.append({"key": key, "label": LABELS[key], "area": area_of(key),
                     "unit": "amount" if key.endswith("amount") else "count", "limit": limit,
                     "used": used, "percent": percent, "level": level(percent)})
    from .extra_quotas import usage_rows as extra_rows  # decision 284 addendum: every other resource
    return rows + extra_rows(makerspace)
