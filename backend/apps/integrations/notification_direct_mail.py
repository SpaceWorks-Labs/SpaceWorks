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
            or log.source_metadata.get("address_owner", True) and envelope.recipient.email != log.to_email):
        return False
    content = external_links(envelope.makerspace, render(envelope))
    set_content(log, to_email=log.to_email, subject=content["subject"], text_body=content["text"],
                html_body=content.get("html", ""))
    return True
