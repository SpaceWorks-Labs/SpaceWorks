"""The canonical record of a provider bounce or complaint (decision #86c).

Both inbound routes land here: the signed generic ``email-bounce-webhook`` and the
native Resend/Mailgun ``email-provider-webhook``, which forwards after verifying the
provider's own signature. One tenant-bound ``EmailProviderEvent`` per event id makes a
replay a no-op, and the log stamp, suppression and audit rows are written once.
Callers hold ``tenant_write`` for the space.
"""

from django.utils import timezone

from apps.accounts import rbac
from apps.audit import services as audit
from apps.integrations.models_email import EmailLog
from apps.integrations.models_suppression import EmailSuppression
from apps.integrations.models_tracking import EmailProviderEvent


def record_provider_event(space, *, event_id, reason, recipient_hash, logs=None):
    """Record one bounce/complaint; returns False when the event was already recorded."""
    _, fresh = EmailProviderEvent.objects.get_or_create(
        makerspace=space, event_id=event_id, defaults={"reason": reason},
    )
    if not fresh:
        return False
    if logs is not None:
        field = "complained_at" if reason == "complaint" else "bounced_at"
        scoped = rbac.scope_notification_policy(EmailLog.objects.all(), makerspace_id=space.pk)
        scoped.filter(pk__in=logs.values("pk"), **{field + "__isnull": True}).update(**{field: timezone.now()})
    audit.record(None, "email.provider_event_received", makerspace=space, meta={"reason": reason})
    rows = rbac.scope_notification_policy(EmailSuppression.objects.all(), makerspace_id=space.pk)
    row, created = rows.get_or_create(makerspace=space, address_hash=recipient_hash, defaults={"reason": reason})
    row = rbac.scope_notification_policy(
        EmailSuppression.objects.select_for_update(), makerspace_id=space.pk).get(pk=row.pk)
    changed = reason == "complaint" and row.reason != "complaint"
    if changed:
        row.reason = "complaint"
        row.save(update_fields=["reason"])
    if created or changed:
        audit.record(None, "email.suppressed_provider", makerspace=space, target=row, meta={"reason": row.reason})
    return True
