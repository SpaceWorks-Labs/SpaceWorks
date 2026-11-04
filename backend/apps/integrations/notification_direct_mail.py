"""Keep compatibility mail attached to its envelope and reserve the email leg."""
from .models_contract import NotificationEnvelope
from .models import EmailLog
from django.db.models import Q

KIND = "notification.direct"


def reserved(envelope):
    return EmailLog.objects.filter(makerspace_id=envelope.makerspace_id).filter(
        Q(source_kind=KIND, source_id=envelope.pk) | Q(source_metadata__p2_direct=envelope.dedup_key),
    ).exclude(status="skipped").exists()


def prepare(log):
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
