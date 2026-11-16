"""Claims never infer non-delivery from lease expiry; completions are token-fenced."""
from datetime import timedelta
from uuid import uuid4

from django.db.models import F, Q
from django.utils import timezone

MAX_ATTEMPTS = 4  # Same budget as the canonical parent worker.


def _targets(queryset):
    # Joined tenant/ownership filters stay inside the identity subquery; mutable
    # lease/status predicates belong to the actual UPDATE and its row-lock recheck.
    return queryset.model._base_manager.using(queryset.db).filter(
        pk__in=queryset.order_by().values("pk"),
    )


def due_deliveries(queryset, now=None):
    return queryset.filter(
        Q(status="pending", attempts=0) | Q(status="failed", retryable=True),
        attempts__lt=MAX_ATTEMPTS,
    )


def hold_expired(queryset, now=None):
    # Keep the old token for a proved completion, but never reclaim its provider call.
    return _targets(queryset).filter(Q(lease_until__lte=now or timezone.now()) | Q(lease_until=None),
                           status="sending").update(
        status="held", retryable=False, last_error="unknown_provider_outcome",
    )


def claim(queryset):
    hold_expired(queryset)
    token, now = uuid4(), timezone.now()
    changed = due_deliveries(_targets(queryset)).update(
        status="sending", retryable=False, lease_token=token,
        lease_until=now + timedelta(minutes=2), attempts=F("attempts") + 1, last_error="",
    )
    return token if changed else None


def complete(queryset, token, *, status, error="", retryable=False):
    # An expired worker may settle its OWN held lease with an actual provider fact.
    # Account removal/explicit quarantine clears the token and fences that completion.
    fields = {"status": status, "retryable": bool(retryable), "last_error": error[:200],
              "lease_token": None, "lease_until": None}
    if status == "sent":
        fields["sent_at"] = timezone.now()
    return _targets(queryset).filter(
        Q(status="sending") | Q(status="held", last_error="unknown_provider_outcome"),
        lease_token=token,
    ).update(**fields)


def skip(queryset, reason):
    return due_deliveries(_targets(queryset)).update(
        status="skipped", retryable=False, last_error=reason,
        lease_token=None, lease_until=None,
    )
