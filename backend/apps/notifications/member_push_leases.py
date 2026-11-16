"""Atomic claims and fenced completion; no transaction spans provider I/O."""

from datetime import timedelta
from uuid import uuid4

from django.db.models import F, Q
from django.utils import timezone

MAX_ATTEMPTS = 5


def reclaimable(now):
    return (Q(status__in=("pending", "failed"))
            | Q(status="sending", lease_until__lt=now))


def due_deliveries(queryset, now):
    return queryset.filter(reclaimable(now), attempts__lt=MAX_ATTEMPTS)


def claim(queryset):
    now, token = timezone.now(), uuid4()
    changed = due_deliveries(queryset, now).update(
        status="sending", lease_token=token, lease_until=now + timedelta(minutes=2),
        attempts=F("attempts") + 1, last_error="",
    )
    return token if changed else None


def complete(queryset, token, *, status, error="", exhausted=False):
    fields = {"status": status, "last_error": error[:200], "lease_token": None, "lease_until": None}
    if status == "sent":
        fields["sent_at"] = timezone.now()
    if exhausted:
        fields["attempts"] = MAX_ATTEMPTS
    return queryset.filter(status="sending", lease_token=token).update(**fields)


def skip(queryset, reason):
    # Do not steal a live worker's lease or rewrite terminal history.
    queryset.filter(reclaimable(timezone.now())).update(
        status="skipped", last_error=reason, lease_token=None, lease_until=None,
    )
