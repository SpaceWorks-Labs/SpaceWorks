"""Keep compatibility mail attached to its envelope and reserve the email leg."""
from .models_contract import NotificationEnvelope
from .models import EmailLog
from django.db.models import Q

KIND = "notification.direct"


def reserve_deliveries(envelope, *, fallback=False):
    """All worker, sweep, other-channel retry and fallback reservations enter decide."""
    from apps.tenant_migration.gate_runtime import tenant_write
    from .notification_delivery import _ensure_deliveries
    from .document_email_state import decide, envelope_identity, live_reason
    if envelope.source_kind != "payments.document" or envelope.event != "document_issued":
        with tenant_write(envelope.makerspace_id):
            return _ensure_deliveries(envelope, fallback=fallback)
    # Non-email channels retain their existing resolution and reservation behaviour.
    with tenant_write(envelope.makerspace_id):
        _ensure_deliveries(envelope, fallback=fallback, allow_email=False)

    def reserve():
        _ensure_deliveries(envelope, fallback=fallback)
        return envelope.deliveries.filter(channel="email").first()

    decision = decide(**envelope_identity(envelope), event="reserve", owner_kind="envelope",
        reason=lambda: live_reason(envelope.makerspace, envelope.recipient), perform=reserve)
    envelope._document_dispatch_epoch = decision.intent.generation
    return envelope.deliveries.all()


def reserved(envelope):
    if envelope.source_kind == "payments.document" and envelope.event == "document_issued":
        from .document_email_state import envelope_identity
        from .document_email_history import scoped
        from .models_document_email import DocumentEmailIntent
        # Resolution is advisory. The actual reservation repeats admission under decide's lock.
        return scoped(DocumentEmailIntent, envelope.makerspace_id).filter(
            **envelope_identity(envelope), state="sent").exclude(owner_kind="envelope").exists()
    return EmailLog.objects.filter(makerspace_id=envelope.makerspace_id).filter(
        Q(source_kind=KIND, source_id=envelope.pk) | Q(source_metadata__p2_direct=envelope.dedup_key),
    ).exclude(status="skipped").exists()


def prepare(log):
    from .document_email_dispatch import allow_document_attempt
    if not allow_document_attempt(log):
        return False
    from .notification_resolution import eligible
    from .notification_sources import render
    from .notification_links import external_links
    from .delivery_content import render as set_content
    envelope = NotificationEnvelope.objects.filter(pk=log.source_id, makerspace_id=log.makerspace_id).first()
    if (envelope is None or not eligible(envelope) or log.event != envelope.event
            or log.source_metadata.get("address_owner", True) and log.recipient_id != envelope.recipient_id):
        return False
    envelope.recipient.refresh_from_db()
    document_mail = envelope.source_kind == "payments.document"
    if document_mail and log.recipient_id != envelope.recipient_id:
        return False
    address_owner = document_mail or log.source_metadata.get("address_owner", True)
    if (envelope.source_kind != "payments.document" and address_owner
            and envelope.recipient.email != log.to_email):
        return False
    if not envelope.recipient.email and address_owner:
        return False
    from apps.payments.document_delivery import attachment_references
    content = external_links(envelope.makerspace, render(envelope))
    set_content(log, to_email=envelope.recipient.email if address_owner else log.to_email,
                subject=content["subject"], text_body=content["text"],
                html_body=content.get("html", ""), attachments=attachment_references(envelope))
    return True
