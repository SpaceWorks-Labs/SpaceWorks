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
#: The migration that introduced refund cases. Its apply time is the deploy watermark.
WATERMARK_MIGRATION = ("payments", "0023_refund_cases")


def deploy_watermark():
    """When refund cases were installed on this deployment (decision 72).

    The sweep never looks before it, so the first deploy does not back-fill cases for
    cancellations that happened while the feature did not exist. Django records the
    apply time in `django_migrations` once, durably, and a restore or tenant import
    does not move it. None (no record) means the sweep does nothing: fail closed.
    """
    from django.db.migrations.recorder import MigrationRecorder
    app, name = WATERMARK_MIGRATION
    return MigrationRecorder.Migration.objects.filter(app=app, name=name).values_list("applied", flat=True).first()


def sweep_since(now):
    watermark = deploy_watermark()
    return None if watermark is None else max(now - LOOKBACK, watermark)
PAID = (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE)


def missed_registration_cases(space, *, since, limit):
    """`(payment, reason_code, cancelled_at)` for paid, cancelled registrations with no due case."""
    from apps.events.models import Event, EventRegistration

    cutoff = since
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


def missed_membership_cases(space, *, since, limit):
    """Paid term charges of recently cancelled terms -- the term's own renewal and the one
    that bought it -- that have no due case yet."""
    from apps.audit.models import AuditLog
    from apps.makerspaces.models import MembershipTerm

    cancelled = {}
    for target_id, at in AuditLog.objects.filter(
        makerspace=space, action="membership.term_cancelled", target_type="makerspaces.membershipterm",
        created_at__gte=since,
    ).values_list("target_id", "created_at"):
        cancelled.setdefault(int(target_id), at)
    subjects = {}
    for term_id, renewed_from in MembershipTerm.objects.filter(
        pk__in=list(cancelled), status=MembershipTerm.Status.CANCELLED,
    ).values_list("pk", "renewed_from_id"):
        subjects.setdefault(term_id, cancelled[term_id])
        if renewed_from:
            subjects.setdefault(renewed_from, cancelled[term_id])
    from django.db.models import Q
    started = [term_id for term_id in subjects if term_id in cancelled]  # #184: a staff-opened term's own charge
    payments = (Payment.objects.filter(
        Q(subject_type=Payment.SubjectType.MEMBERSHIP_TERM, subject_id__in=list(subjects))
        | Q(subject_type=Payment.SubjectType.MEMBERSHIP_TERM_START, subject_id__in=started),
        makerspace=space, status__in=PAID,
    ).exclude(refund_cases__kind=RefundCase.Kind.DUE).order_by("pk")[:limit])
    return [(payment, RefundCase.ReasonCode.MEMBERSHIP_CANCELLED, subjects[payment.subject_id]) for payment in payments]


def rebuild_missed_refund_cases(*, makerspace_id=None, limit=200, now=None):
    from apps.separability.tombstones import app_is_tombstoned
    from apps.payments.services_refund_cases import open_due_case

    counts = {"opened": 0, "skipped": 0, "failed": 0}
    events_live = not app_is_tombstoned("events")
    since = sweep_since(now or timezone.now())
    if since is None:
        return counts
    spaces = rbac.scope_for_scheduled_work(Makerspace.objects.all(), field="pk").order_by("pk")
    if makerspace_id is not None:
        spaces = spaces.filter(pk=makerspace_id)
    for space in spaces.iterator(chunk_size=100):
        try:
            with fanout_tenant_write(space.pk, operation="rebuild_refund_cases", counts=counts) as allowed:
                if not allowed:
                    continue
                found = missed_registration_cases(space, since=since, limit=limit) if events_live else []
                for payment, reason, cancelled_at in [*found, *missed_membership_cases(space, since=since, limit=limit)]:
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
