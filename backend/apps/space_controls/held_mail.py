"""Mail held while a space was paused is sent once the pause ends (#185(1), #195).

A paused space's delivery task refuses before it claims the row (the source gate), so
the EmailLog stays PENDING: held, not dropped. The free profile's drain picks such rows
up on its own; the full profile enqueued each row exactly once, so nothing would retry
it. Unpausing therefore re-enqueues the space's held rows after the commit. Quiet-hours
and digest deferrals (``error`` = ``deferred:...``) keep their own release reminder.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

HELD_LIMIT = 5000


def held_mail_ids(makerspace_id, *, now=None):
    from apps.integrations.models import EmailLog
    now = now or timezone.now()
    rows = (EmailLog.objects.filter(makerspace_id=makerspace_id, status=EmailLog.Status.PENDING,
                                    email_retryable=True)
            .filter(Q(email_retry_at__isnull=True) | Q(email_retry_at__lte=now))
            .exclude(error__startswith="deferred:"))
    return list(rows.order_by("pk").values_list("pk", flat=True)[:HELD_LIMIT])


def release_held_mail(makerspace_id):
    """Queue the held rows after the unpause commits; returns how many were found."""
    ids = held_mail_ids(makerspace_id)

    def enqueue():
        from apps.integrations.dispatch_outbox import _enqueue
        for pk in ids:
            _enqueue(pk)

    if ids:
        transaction.on_commit(enqueue)
    return len(ids)
