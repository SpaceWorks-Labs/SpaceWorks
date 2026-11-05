"""X49 ticket designs (`card_designs` domain `event_ticket`): render a registrant's ticket.

Exactly one check-in QR, on a white plate: the desk-QR slot carries the registration's
own check-in payload. Per ticket type, then the event, then the organisation library
default. The FK lives on `CardDesign`, never on the ticket model. L6 owns the event
confirmation email and attaches this PDF through `render_ticket` (the contract).
"""
from django.utils.text import slugify
from rest_framework.exceptions import NotFound

from apps.card_designs.holders_member import fmt_date


def ticket_payload(registration):
    if registration.credential_mode == "v2" and registration.member_id:
        from .credentials.workflow import owner_payload
        return owner_payload(registration, actor=registration.member)
    if registration.credential_mode == "legacy":
        return str(registration.checkin_token)
    return None


def render_ticket(registration, *, fmt="pdf"):
    """-> (filename, bytes, content type). Raises NotFound when tickets are off or no design."""
    from apps.card_designs.layout import normalize_document
    from apps.card_designs.rendering import RenderContext, render_pdf, render_png
    from apps.card_designs.resolution import resolve
    from apps.card_designs.switches import domain_on
    from .contributions.crew_reads import crew_labels
    from .id_cards_holder import _organisers
    event = registration.event
    if not domain_on(event.makerspace, "event_ticket"):
        raise NotFound()
    document, design = resolve(event.makerspace_id, "event_ticket", event_id=event.pk,
                               ticket_type_id=registration.ticket_type_id,
                               organization_ids=[row.organization_id for row in _organisers(event)])
    document = normalize_document(document, check_contrast=False)
    values = {"name": registration.name, "event": event.title, "number": f"EV-{event.pk}-{registration.pk}",
              "plan": registration.ticket_type.name if registration.ticket_type_id else "Ticket",
              "valid_until": fmt_date(event.ends_at), "issued_on": fmt_date(registration.created_at),
              "space": event.makerspace.name,
              "role": crew_labels(event, [registration.pk]).get(registration.pk, "Attendee")}
    context = RenderContext(values=values, desk_qr=ticket_payload(registration))
    name = slugify(f"ticket-{event.pk}-{registration.name}")[:80] or f"ticket-{registration.pk}"
    if fmt == "png":
        return f"{name}.png", render_png(document, context), "image/png"
    return f"{name}.pdf", render_pdf(document, context, title=name), "application/pdf"
