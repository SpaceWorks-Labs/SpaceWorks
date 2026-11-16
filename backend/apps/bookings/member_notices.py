"""Member dashboard notices for booking decisions, derived only from the member's own bookings.

The member dashboard serves facts about the reader (never the tenant-wide notification
table), so these are computed from the reader's own `Booking` rows: a recent approval,
a recent rejection or staff cancellation with its reason, and finished bookings still
waiting for a check-out remark.
"""

from datetime import timedelta

from django.utils.translation import gettext

from apps.makerspaces.platform import module_enabled

RECENT = timedelta(days=14)
LIMIT = 5


def booking_notices(membership, now):
    from .models import Booking
    from .services_departure import MEMBER_GRACE_AFTER_END
    makerspace = membership.makerspace
    if not module_enabled(makerspace, "bookings"):
        return []
    rows = Booking.objects.filter(space__makerspace=makerspace, member_id=membership.user_id).select_related("space")
    feed = []
    for row in rows.filter(status="rejected", calendar_updated_at__gte=now - RECENT).order_by("-calendar_updated_at")[:LIMIT]:
        feed.append({"level": "warning", "event": "booking_rejected", "title": gettext("Booking request for %(space)s was declined") % {"space": row.space.name},
                     "body": row.decision_reason or gettext("Staff could not approve this request.")})
    cancelled = rows.filter(status="cancelled", calendar_updated_at__gte=now - RECENT).exclude(decision_reason="")
    for row in cancelled.order_by("-calendar_updated_at")[:LIMIT]:
        feed.append({"level": "warning", "event": "booking_cancelled", "title": gettext("Your booking for %(space)s was cancelled") % {"space": row.space.name},
                     "body": row.decision_reason})
    approved = rows.filter(status="confirmed", ends_at__gt=now, calendar_updated_at__gte=now - RECENT,
                           space__approval_mode="approve").order_by("starts_at")[:LIMIT]
    for row in approved:
        feed.append({"level": "info", "event": "booking_confirmed", "title": gettext("Booking confirmed: %(space)s") % {"space": row.space.name},
                     "body": gettext("Starts %(when)s.") % {"when": row.starts_at.isoformat()}})
    awaiting = rows.filter(status__in=("confirmed", "completed"), departed_at__isnull=True, ends_at__lte=now,
                           ends_at__gte=now - MEMBER_GRACE_AFTER_END).count()
    if awaiting:
        feed.append({"level": "info", "event": "booking_checkout_due", "title": gettext("%(count)s booking(s) to check out") % {"count": awaiting},
                     "body": gettext("Tell the space how it went, and report anything that was wrong.")})
    return feed
