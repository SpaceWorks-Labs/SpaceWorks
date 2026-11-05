"""The email delivery source and typed attachments for "your card" mail.

`prepare(log)` runs at every send and retry: it reloads the card, re-checks that it is
still valid, still switched on and still addressed to the holder's current email,
and rebuilds the message. Each attachment is an `AttachmentReference` resolved by
`notification_attachment_sources` at send time; nothing renders it earlier and no
bytes are ever stored. Email-only: card files never go to chat channels.

The holder's `email_format` picks the files, read at send time: the PDF (reference
kind = the holder kind, as before), or one PNG per side (reference kind
`<holder kind>:png:<side>`). A kind the parser does not know is refused.
"""
from django.utils import timezone

from .email import SOURCE_KIND, body_for, subject_for
from .holders import registered

SIDES = ("front", "back")


def revision(card):
    stamp = getattr(card, "issued_at", None) or getattr(card, "created_at", None) or timezone.now()
    return str(int(stamp.timestamp()))


def parse_kind(value):
    """-> (holder kind, format, side) from an attachment reference kind."""
    holder, _sep, rest = str(value).partition(":")
    if not rest:
        return holder, "pdf", "front"
    fmt, _sep, side = rest.partition(":")
    if fmt != "png" or side not in SIDES:
        return None, None, None
    return holder, fmt, side


def references_for(kind, card):
    if getattr(card, "email_format", "pdf") != "png":
        return ((kind, revision(card)),)
    spec = registered().get(kind)
    document, _design = spec.design(card) if spec else ({}, None)
    sides = SIDES if (document or {}).get("back_enabled") else SIDES[:1]
    return tuple((f"{kind}:png:{side}", revision(card)) for side in sides)


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
        attachments = tuple(AttachmentReference(SOURCE_KIND, card.pk, ref_kind, stamp)
                            for ref_kind, stamp in references_for(kind, card))
    render(log, to_email=address, subject=subject_for(kind, values), text_body=text, html_body=html,
           attachments=attachments)
    return True


def authorize(reference, *, makerspace_id, recipient_id):
    from apps.integrations.notification_attachment_sources import DocumentDeliveryError
    holder, _fmt, _side = parse_kind(reference.kind)
    spec, card = _load(holder, reference.document_id) if holder else (None, None)
    if (card is None or card.makerspace_id != makerspace_id or spec.account_id(card) != recipient_id
            or spec.standing(card) != "valid" or not spec.switched_on(card) or revision(card) != reference.revision):
        raise DocumentDeliveryError("document_not_authorized")
    return card


def render_attachment(reference, *, makerspace_id, recipient_id):
    from apps.integrations.notification_attachment_sources import DocumentDeliveryError
    from .cards import render
    card = authorize(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
    holder, fmt, side = parse_kind(reference.kind)
    try:
        data, content_type, filename = render(holder, card, fmt=fmt, side=side)
    except Exception:
        raise DocumentDeliveryError("document_render_failed") from None
    return filename, data, content_type


def register():
    from apps.integrations.delivery_sources import DeliverySource, register as register_delivery
    from apps.integrations.notification_attachment_sources import AttachmentSource, register_source
    register_delivery(SOURCE_KIND, DeliverySource(prepare, digestible=False))
    register_source(SOURCE_KIND, AttachmentSource(lambda envelope: (), authorize, render_attachment, None,
                                                  lambda card: (card.makerspace_id,)))
