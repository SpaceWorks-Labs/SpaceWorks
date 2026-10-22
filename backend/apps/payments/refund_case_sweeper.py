"""Rebuild refund cases a cancellation hook failed to open (R6). Idempotent, bounded.

The events path deliberately swallows payment errors so a provider or database hiccup
never undoes a cancellation -- which means a paid registration can be cancelled with
no case recording what the member is owed. This sweep finds those, through one defined
selector, and hands each to `open_due_case`, which dedupes under the Payment lock, so a
case is never opened twice however often the sweep runs.

Membership term cancellation also swallows payment errors (decision 68), so cancelled
terms are swept too, timed by their `membership.term_cancelled` audit entry. Bookings
need no sweep: their case commits in the cancellation's own transaction (BK-0). A
tombstoned events app has no registrations to read, so only that half is skipped.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.payments.models import Payment, RefundCase
from apps.tenant_migration.gate_runtime import fanout_tenant_write

logger = logging.getLogger(__name__)
LOOKBACK = timedelta(days=7)
PAID = (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE)


def missed_registration_cases(space, *, now, limit):
    """`(payment, reason_code, cancelled_at)` for paid, cancelled registrations with no due case."""
    from apps.events.models import Event, EventRegistration

    cutoff = now - LOOKBACK
    standing = EventRegistration.objects.filter(
        event__makerspace=space, event__status=Event.Status.CANCELLED, event__updated_at__gte=cutoff,
    ).exclude(status__in=(EventRegistration.Status.CANCELLED, EventRegistration.Status.REJECTED))
    member_cancelled = EventRegistration.objects.filter(
        event__makerspace=space, status=EventRegistration.Status.CANCELLED, cancelled_at__gte=cutoff,
    )
    found = []
    for reason, rows in ((RefundCase.ReasonCode.EVENT_CANCELLED, standing),
                         (RefundCase.ReasonCode.REGISTRATION_CANCELLED, member_cancelled)):
        cancelled = dict(rows.values_list("pk", "cancelled_at"))
        payments = (Payment.objects.filter(
            makerspace=space, subject_type=Payment.SubjectType.EVENT_REGISTRATION,
            subject_id__in=list(cancelled), status__in=PAID,
        ).exclude(refund_cases__kind=RefundCase.Kind.DUE).order_by("pk")[:limit])
        found.extend((payment, reason, cancelled[payment.subject_id]) for payment in payments)
    return found


def missed_membership_cases(space, *, now, limit):
    """Paid term charges of recently cancelled terms -- the term's own renewal and the one
    that bought it -- that have no due case yet."""
    from apps.audit.models import AuditLog
    from apps.makerspaces.models import MembershipTerm

    cancelled = {}
    for target_id, at in AuditLog.objects.filter(
        makerspace=space, action="membership.term_cancelled", target_type="makerspaces.membershipterm",
        created_at__gte=now - LOOKBACK,
    ).values_list("target_id", "created_at"):
        cancelled.setdefault(int(target_id), at)
    subjects = {}
    for term_id, renewed_from in MembershipTerm.objects.filter(
        pk__in=list(cancelled), status=MembershipTerm.Status.CANCELLED,
    ).values_list("pk", "renewed_from_id"):
        subjects.setdefault(term_id, cancelled[term_id])
        if renewed_from:
            subjects.setdefault(renewed_from, cancelled[term_id])
    payments = (Payment.objects.filter(
        makerspace=space, subject_type=Payment.SubjectType.MEMBERSHIP_TERM, subject_id__in=list(subjects),
        status__in=PAID,
    ).exclude(refund_cases__kind=RefundCase.Kind.DUE).order_by("pk")[:limit])
    return [(payment, RefundCase.ReasonCode.MEMBERSHIP_CANCELLED, subjects[payment.subject_id]) for payment in payments]


def rebuild_missed_refund_cases(*, makerspace_id=None, limit=200, now=None):
    from apps.separability.tombstones import app_is_tombstoned
    from apps.payments.services_refund_cases import open_due_case

    counts = {"opened": 0, "skipped": 0, "failed": 0}
    events_live = not app_is_tombstoned("events")
    now = now or timezone.now()
    spaces = rbac.scope_for_scheduled_work(Makerspace.objects.all(), field="pk").order_by("pk")
    if makerspace_id is not None:
        spaces = spaces.filter(pk=makerspace_id)
    for space in spaces.iterator(chunk_size=100):
        try:
            with fanout_tenant_write(space.pk, operation="rebuild_refund_cases", counts=counts) as allowed:
                if not allowed:
                    continue
                found = missed_registration_cases(space, now=now, limit=limit) if events_live else []
                for payment, reason, cancelled_at in [*found, *missed_membership_cases(space, now=now, limit=limit)]:
                    try:
                        case = open_due_case(payment, reason_code=reason, actor=None,
                                             cancelled_at=None if reason == RefundCase.ReasonCode.EVENT_CANCELLED
                                             else cancelled_at)
                        counts["opened" if case else "skipped"] += 1
                    except Exception as exc:
                        counts["failed"] += 1
                        logger.error("refund_case_rebuild_failed", extra={
                            "payment_id": payment.pk, "failure_type": type(exc).__name__})
        except Exception as exc:
            counts["failed"] += 1
            logger.error("refund_case_rebuild_tenant_failed", extra={
                "makerspace_id": space.pk, "failure_type": type(exc).__name__})
    return counts
