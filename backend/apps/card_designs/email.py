"""Email a holder their card (SPEC §6 "Email your card"), as a PDF or as PNG images.

The holder chooses the attachment (`email_format` on the card: the PDF, or one 300-dpi
PNG per side); staff and bulk sends use that choice too.

Limits: one email per card per 24 h for bulk and automatic sends; an explicit single
"Email card" again after 10 minutes; at most 200 card emails per space per day (50 for
a space younger than 7 days). The `email` module gate applies. The message row carries
only the card id and revision: the PDF is rendered at send time and dropped when the
card was revoked, the holder erased, the address changed or the space unservable.
"""
from datetime import timedelta

from django.utils import timezone

from apps.integrations.fanout_jobs import deferred_fanout
from apps.audit import services as audit

from .holders import registered

SOURCE_KIND = "card_designs.card"
STREAMS = {"member_card": "membership", "programme_card": "membership", "event_card": "events"}
EXPLICIT_COOLDOWN = timedelta(minutes=10)
BULK_COOLDOWN = timedelta(hours=24)
DAILY_CAP, NEW_SPACE_CAP = 200, 50


def daily_cap(makerspace):
    young = makerspace.created_at and makerspace.created_at > timezone.now() - timedelta(days=7)
    return NEW_SPACE_CAP if young else DAILY_CAP


def sent_today(makerspace):
    from apps.integrations.models import EmailLog
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return EmailLog.objects.filter(makerspace=makerspace, source_kind=SOURCE_KIND, created_at__gte=start).count()


def blocked(makerspace):
    from apps.integrations.dispatch_policy import email_module_blocks
    return email_module_blocks(makerspace, "membership", "card_issued")


def subject_for(kind, values):
    if kind == "programme_card":
        return f"Your {values.get('programme') or 'ID'} card from {values.get('organisation') or values.get('space')}"
    if kind == "event_card":
        return f"Your {values.get('event') or 'event'} ID card"
    return f"Your {values.get('space')} member card"


def attachment_note(card):
    if getattr(card, "email_format", "pdf") == "png":
        return "Your card is attached as PNG images (front, and back when it has one)."
    return "Your card is attached as a PDF."


def body_for(kind, card, values):
    from django.conf import settings
    from django.utils.html import escape
    base = (getattr(settings, "PUBLIC_APP_BASE_URL", "") or "").rstrip("/")
    link = f"{base}/member/cards"
    lines = [f"Hello {values.get('name', '')},", "", attachment_note(card),
             f"Number: {values.get('number', '')}", f"Valid until: {values.get('valid_until', '')}", "",
             f"See it any time under My cards: {link}"]
    html = ("<div style=\"font-family:Outfit,Arial,sans-serif;max-width:420px;border:1px solid #D5D0C6;"
            "border-radius:16px;overflow:hidden\"><div style=\"background:#006E63;color:#FFF4E8;padding:14px 18px\">"
            f"<div style=\"font-size:11px;letter-spacing:.08em;text-transform:uppercase\">{escape(values.get('space', ''))}"
            f"</div><div style=\"font-size:20px;font-weight:700\">{escape(values.get('name', ''))}</div></div>"
            "<div style=\"padding:14px 18px;color:#142C2A\"><div style=\"font-size:11px;text-transform:uppercase\">Number"
            f"</div><div style=\"font-size:14px;font-weight:700\">{escape(values.get('number', ''))}</div>"
            "<div style=\"font-size:11px;text-transform:uppercase;margin-top:8px\">Valid until</div>"
            f"<div style=\"font-size:14px;font-weight:700\">{escape(values.get('valid_until', ''))}</div>"
            f"<p><a href=\"{escape(link)}\">Open My cards</a></p></div></div>")
    return "\n".join(lines), html


@deferred_fanout()
def _queue_card_email(kind, card):
    """Worker side of send_card_email: render the card email and write its outbox row.

    ``card.updated_at`` and the other state columns are the values at the call (see fanout_codec), so the
    revision recorded here is the one the caller decided on.
    """
    from apps.integrations.dispatch_outbox import dispatch_email
    spec = registered().get(kind)
    if spec is None:
        return
    values = spec.snapshot(card)
    text, html = body_for(kind, card, values)
    dispatch_email(to_email=spec.email(card), subject=subject_for(kind, values), text_body=text, html_body=html,
                   makerspace=card.makerspace, stream=STREAMS[kind], event="card_issued", audience="requester",
                   recipient_id=spec.account_id(card), source_kind=SOURCE_KIND, source_id=card.pk,
                   source_metadata={"holder_kind": kind, "revision": card.updated_at.isoformat(),
                                    "format": getattr(card, "email_format", "pdf")})


def send_card_email(kind, card, *, actor=None, explicit=False):
    """Queue one card email; -> True when it was queued, False when a limit or rule refused it."""
    spec = registered().get(kind)
    if spec is None or spec.standing(card) != "valid" or not spec.switched_on(card):
        return False
    space = card.makerspace
    address = spec.email(card)
    now = timezone.now()
    cooldown = EXPLICIT_COOLDOWN if explicit else BULK_COOLDOWN
    if not address or blocked(space) or (card.last_emailed_at and card.last_emailed_at > now - cooldown):
        return False
    if sent_today(space) >= daily_cap(space):
        return False
    _queue_card_email(kind, card)  # snapshot, body rendering and the outbox row happen in the worker
    type(card).objects.filter(pk=card.pk).update(last_emailed_at=now)
    if kind == "member_card":
        audit.record(actor, "member_card.emailed", makerspace=space, target=card, meta={"card_id": card.pk, "count": 1})
    elif kind == "programme_card":
        audit.record(actor, "id_programme.card_emailed", makerspace=space, target=card,
                     meta={"card_id": card.pk, "count": 1})
    else:
        audit.record(actor, "event_card.emailed", makerspace=space, target=card, meta={"card_id": card.pk, "count": 1})
    return True
