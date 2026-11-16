"""Decision 242(l) / U7-U10: superadmin cross-space queues, snapshots, unread inbox and platform search.

Counts only, never tenant rows: one grouped query per metric across the servable spaces (no N+1). These are
platform-only builders; the views mint the superadmin check, audit every read of the inbox and search, and
throttle both. Search returns kinds and space ids/names (a space, a person's account, a receipt number's
space), never anything from inside a space.
"""

from django.db.models import Q
from django.utils import timezone

from apps.makerspaces.servability import servable_queryset
from apps.operations.platform_overview_blocks import count_by_space

METRICS = ("pending_requests", "awaiting_issue", "overdue_loans", "pending_bookings", "pending_registrations",
           "refund_cases_open", "paid_claims_open", "open_incidents", "critical_incidents", "open_booking_issues",
           "shop_orders_waiting", "pending_payments")


def servable_spaces():
    return list(servable_queryset().order_by("name", "pk").values("pk", "name", "slug"))


def metric_counts(ids, now=None):
    """`{metric: {space_id: n}}` for the given spaces; every metric is one grouped query."""
    from apps.bookings.models import Booking
    from apps.bookings.models_departure import BookingIssue
    from apps.events.models import EventRegistration
    from apps.hardware_requests.models import HardwareRequest
    from apps.maintenance.incidents.models import Incident
    from apps.payments.models import Payment, PaymentClaim, RefundCase
    from apps.shop.models import ShopOrder

    now = now or timezone.now()
    requests = HardwareRequest.objects.filter(makerspace_id__in=ids)
    incidents = Incident.objects.filter(makerspace_id__in=ids, status__in=Incident.OPEN_STATUSES)
    return {
        "pending_requests": count_by_space(requests.filter(status=HardwareRequest.Status.PENDING_APPROVAL)),
        "awaiting_issue": count_by_space(requests.filter(status=HardwareRequest.Status.ACCEPTED)),
        "overdue_loans": count_by_space(requests.filter(status__in=("issued", "partially_returned"),
                                                       return_due_at__lt=now)),
        "pending_bookings": count_by_space(Booking.objects.filter(
            space__makerspace_id__in=ids, status=Booking.Status.PENDING), "space__makerspace_id"),
        "pending_registrations": count_by_space(EventRegistration.objects.filter(
            event__makerspace_id__in=ids, status="pending_approval"), "event__makerspace_id"),
        "refund_cases_open": count_by_space(RefundCase.objects.filter(
            payment__makerspace_id__in=ids, status__in=RefundCase.ACTIVE_STATUSES), "payment__makerspace_id"),
        "paid_claims_open": count_by_space(PaymentClaim.objects.filter(
            makerspace_id__in=ids, status__in=PaymentClaim.OPEN_STATUSES)),
        "open_incidents": count_by_space(incidents),
        "critical_incidents": count_by_space(incidents.filter(severity__in=("high", "critical"))),
        "open_booking_issues": count_by_space(BookingIssue.objects.filter(
            makerspace_id__in=ids, resolved_at__isnull=True)),
        "shop_orders_waiting": count_by_space(ShopOrder.objects.filter(
            makerspace_id__in=ids, status__in=(ShopOrder.Status.AWAITING_PAYMENT, ShopOrder.Status.PAID))),
        "pending_payments": count_by_space(Payment.objects.filter(makerspace_id__in=ids, status=Payment.Status.PENDING)),
    }


def queues_by_space(now=None):
    spaces = servable_spaces()
    counts = metric_counts([row["pk"] for row in spaces], now)
    rows = [{"id": row["pk"], "name": row["name"], "slug": row["slug"],
             "counts": {metric: counts[metric].get(row["pk"], 0) for metric in METRICS}} for row in spaces]
    for row in rows:
        row["total"] = sum(row["counts"].values())
    return rows


def space_snapshot(space, now=None):
    """One space's counts plus its usage. Usage is ALWAYS shown, Own spaces included (limits stay null)."""
    from apps.makerspaces.usage_snapshot import usage_snapshot
    from apps.managed_hosting.hosting_type import is_hosted

    counts = metric_counts([space.pk], now)
    return {"id": space.pk, "name": space.name, "slug": space.slug, "hosted": bool(is_hosted(space)),
            "counts": {metric: counts[metric].get(space.pk, 0) for metric in METRICS},
            "usage": usage_snapshot(space)}


def unread_by_space(actor):
    """The caller's own unread inbox rows and each space's unread space-wide notices, per space (counts only)."""
    from apps.notifications.models import Notification
    from apps.notifications.models_inbox import NotificationInboxRow

    ids = [row["pk"] for row in servable_spaces()]
    personal = count_by_space(NotificationInboxRow.objects.filter(
        user=actor, makerspace_id__in=ids, read_at__isnull=True, archived_on__isnull=True))
    notices = count_by_space(Notification.objects.filter(makerspace_id__in=ids, read_at__isnull=True))
    names = {row["pk"]: row["name"] for row in servable_spaces()}
    return [{"id": pk, "name": names[pk], "personal_unread": personal.get(pk, 0), "notices_unread": notices.get(pk, 0)}
            for pk in ids if personal.get(pk) or notices.get(pk)]


def platform_search(term, limit=10):
    """Spaces, people (by account) and receipt numbers. Hits name a space and a kind, never in-space rows."""
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership
    from apps.payments.models import PaymentDocument

    spaces = servable_queryset()
    hits = [{"kind": "space", "space_id": s.pk, "label": s.name} for s in spaces.filter(
        Q(name__icontains=term) | Q(slug__icontains=term)).order_by("name")[:limit]]
    people = User.objects.filter(Q(username__icontains=term) | Q(email__iexact=term)).order_by("pk")[:limit]
    for user in people:
        member_of = list(MakerspaceMembership.objects.filter(user=user, makerspace__in=spaces).values_list(
            "makerspace_id", flat=True)[:5])
        hits.append({"kind": "person", "account_id": user.pk, "label": user.username, "space_ids": member_of})
    for doc in PaymentDocument.objects.filter(number__iexact=term, makerspace__in=spaces)[:limit]:
        hits.append({"kind": "receipt", "space_id": doc.makerspace_id, "label": doc.number})
    return hits
