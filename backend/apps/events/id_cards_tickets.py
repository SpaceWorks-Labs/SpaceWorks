"""X49 ticket designs (`card_designs` domain `event_ticket`): render a registrant's ticket.

Exactly one check-in QR, on a white plate: the desk-QR slot carries the registration's
own check-in payload. Per ticket type, then the event, then the organisation library
default. The FK lives on `CardDesign`, never on the ticket model. L6 owns the event
confirmation email and attaches this PDF through `render_ticket` (the contract).
"""
from django.utils.text import slugify
from django.utils.translation import gettext
from rest_framework.exceptions import APIException, NotFound

from apps.card_designs.holders_member import fmt_date


class TicketUsed(APIException):
    """The designed ticket is withdrawn once its holder has checked in, like the live tear-off (parity E-B2, D17)."""
    status_code = 410
    default_detail = "This ticket has been used."
    default_code = "ticket_used"


def _event_local(event, moment):
    from zoneinfo import ZoneInfo
    try:
        return moment.astimezone(ZoneInfo(event.timezone_name))
    except Exception:
        return moment


def merge_values(registration):
    """E-B2 (D17): date, time, venue, price, order and team merge fields for the ticket designer."""
    from .id_cards_holder import team_for
    event = registration.event
    start, end = _event_local(event, event.starts_at), _event_local(event, event.ends_at)
    ticket_type = registration.ticket_type if registration.ticket_type_id else None
    price = ""
    if ticket_type is not None:
        from apps.payments.money import money_text
        if ticket_type.amount:
            from apps.payments.donations.services import space_currency
            price = f"{space_currency(event.makerspace)} {money_text(ticket_type.amount)}".strip()
        else:
            price = gettext("Free")
    seat = getattr(registration, "order_seat", None)
    return {"date": fmt_date(start), "time": f"{start:%H:%M} – {end:%H:%M}",
            "venue": (event.location or event.venue_address or "")[:120], "price": price,
            "order": f"ORD-{seat.order_id}" if seat is not None else "",
            "team": team_for(event.pk, registration.member_id)[0]}


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
    if registration.status == "attended":
        raise TicketUsed()
    document, design = resolve(event.makerspace_id, "event_ticket", event_id=event.pk,
                               ticket_type_id=registration.ticket_type_id,
                               organization_ids=[row.organization_id for row in _organisers(event)])
    document = normalize_document(document, check_contrast=False)
    values = {"name": registration.name, "event": event.title, "number": f"EV-{event.pk}-{registration.pk}",
              "plan": registration.ticket_type.name if registration.ticket_type_id else "Ticket",
              "valid_until": fmt_date(event.ends_at), "issued_on": fmt_date(registration.created_at),
              "space": event.makerspace.name,
              "role": crew_labels(event, [registration.pk]).get(registration.pk, "Attendee"),
              **merge_values(registration)}
    context = RenderContext(values=values, desk_qr=ticket_payload(registration))
    name = slugify(f"ticket-{event.pk}-{registration.name}")[:80] or f"ticket-{registration.pk}"
    if fmt == "png":
        return f"{name}.png", render_png(document, context), "image/png"
    return f"{name}.pdf", render_pdf(document, context, title=name), "application/pdf"
