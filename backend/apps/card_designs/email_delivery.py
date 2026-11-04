"""The email delivery source and typed PDF attachment for "your card" mail.

`prepare(log)` runs at every send and retry: it reloads the card, re-checks that it is
still valid, still switched on and still addressed to the holder's current email,
and rebuilds the message. The PDF is an `AttachmentReference` resolved by
`notification_attachment_sources` at send time; nothing renders it earlier and no
bytes are ever stored. Email-only: card PDFs never go to chat channels.
"""
from django.utils import timezone

from .email import SOURCE_KIND, body_for, subject_for
from .holders import registered


def revision(card):
    stamp = getattr(card, "issued_at", None) or getattr(card, "created_at", None) or timezone.now()
    return str(int(stamp.timestamp()))


def _load(kind, card_id):
    spec = registered().get(kind)
    if spec is None:
        return None, None
    return spec, spec.model().objects.filter(pk=card_id).first()


def prepare(log):
    from apps.integrations.delivery_content import render
    from apps.integrations.notification_attachment_sources import AttachmentReference
    from apps.makerspaces.servability import is_servable
    kind = (log.source_metadata or {}).get("holder_kind")
    spec, card = _load(kind, log.source_id)
    if (card is None or card.makerspace_id != log.makerspace_id or spec.standing(card) != "valid"
            or not spec.switched_on(card) or not is_servable(card.makerspace)):
        return False
    address = spec.email(card)
    if not address or address != log.to_email or spec.account_id(card) != log.recipient_id:
        return False
    values = spec.snapshot(card)
    text, html = body_for(kind, card, values)
    attachments = ()
    if log.recipient_id:
        attachments = (AttachmentReference(SOURCE_KIND, card.pk, kind, revision(card)),)
    render(log, to_email=address, subject=subject_for(kind, values), text_body=text, html_body=html,
           attachments=attachments)
    return True


def authorize(reference, *, makerspace_id, recipient_id):
    from apps.integrations.notification_attachment_sources import DocumentDeliveryError
    spec, card = _load(reference.kind, reference.document_id)
    if (card is None or card.makerspace_id != makerspace_id or spec.account_id(card) != recipient_id
            or spec.standing(card) != "valid" or not spec.switched_on(card) or revision(card) != reference.revision):
        raise DocumentDeliveryError("document_not_authorized")
    return card


def render_attachment(reference, *, makerspace_id, recipient_id):
    from apps.integrations.notification_attachment_sources import DocumentDeliveryError
    from .cards import render
    card = authorize(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
    try:
        pdf, _content_type, filename = render(reference.kind, card, fmt="pdf")
    except Exception:
        raise DocumentDeliveryError("document_render_failed") from None
    return filename, pdf, "application/pdf"


def register():
    from apps.integrations.delivery_sources import DeliverySource, register as register_delivery
    from apps.integrations.notification_attachment_sources import AttachmentSource, register_source
    register_delivery(SOURCE_KIND, DeliverySource(prepare, digestible=False))
    register_source(SOURCE_KIND, AttachmentSource(lambda envelope: (), authorize, render_attachment, None,
                                                  lambda card: (card.makerspace_id,)))
