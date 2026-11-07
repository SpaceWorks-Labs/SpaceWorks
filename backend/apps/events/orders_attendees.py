"""Order seats and the people they are held for (release 2 L6, G27).

A placed order holds one seat per admission (`quantity x seats_per_ticket`). The buyer's
own seat names the buyer; the others name an attendee email or nothing yet. Once the
order is paid, every named seat gets a claim invite: a single-use link whose token is
stored only as a SHA-256 digest. The attendee signs in (creating an account if they have
none) with the address the seat names and claims it; only then does the seat become a
registration (`orders_claims`). The buyer can fill in or change a missing email and
chase an attendee who has not claimed yet. Unclaimed seats stay visible to the buyer
and to the organiser.
"""

from django.utils.translation import gettext
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record

from .models import EventOrder, EventOrderLine, EventOrderSeat
from .orders_errors import OrderRefused

CHASE_COOLDOWN = timedelta(hours=24)


def token_digest(token):
    return hashlib.sha256(str(token or "").encode()).hexdigest()


def claim_url(token):
    base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return f"{base}/member/ticket-claims/{token}"


def create_seats(order, *, attendees=(), buyer_attends=True):
    """One unclaimed seat per admission; the buyer's first (member tickets first)."""
    if buyer_attends and order.event.registrations.filter(
            member=order.buyer, status__in=("pending_approval", "registered", "waitlisted", "attended")).exists():
        raise OrderRefused("already_registered", "You already have a place at this event; buy for others only.")
    lines = sorted(order.lines.filter(kind=EventOrderLine.Kind.TICKET).select_related("ticket_type"),
                   key=lambda line: (line.ticket_type.audience != "member", line.pk))
    emails = list(attendees)
    if buyer_attends:
        emails.insert(0, (order.buyer.email or "").strip().lower())
    for line in lines:
        for _ in range(line.quantity * line.seats_per_unit):
            EventOrderSeat.objects.create(makerspace=order.makerspace, order=order, line=line, event=order.event,
                                          attendee_email=emails.pop(0) if emails else "")
    if any(line.ticket_type.audience == "member" for line in lines) and not buyer_attends:
        raise OrderRefused("order_limit", "A member ticket admits the buyer only.")


def is_buyer_seat(seat):
    email = (seat.order.buyer.email or "").strip().lower()
    return bool(email) and seat.attendee_email.strip().lower() == email


def send_invite(seat, *, actor=None, chase=False):
    """Mint a fresh claim token for a named seat and email the link. Never stores the token."""
    from apps.operations.notifications_p2 import direct_mail_unless_routed
    if seat.status != EventOrderSeat.Status.UNCLAIMED or not seat.attendee_email:
        return False
    token = secrets.token_urlsafe(32)
    now = timezone.now()
    seat.claim_token_digest = token_digest(token)
    seat.invited_at = seat.invited_at or now
    if chase:
        seat.reminded_at = now
    seat.save(update_fields=["claim_token_digest", "invited_at", "reminded_at"])
    event, space = seat.event, seat.makerspace
    buyer = seat.order.buyer.display_name or seat.order.buyer.get_full_name() or "Someone"
    text = (f"{buyer} has a ticket for you to {event.title} at {space.name}.\n"
            f"Sign in or create your account with this email address, then claim your place here:\n"
            f"{claim_url(token)}\n" + ("This is a reminder: the place is still waiting for you.\n" if chase else ""))
    direct_mail_unless_routed(space=space, source_kind="events.ticket_claim", row=seat,
                              revision=seat.claim_token_digest[:16], event="ticket_claim_invite",
                              owner=None, to_email=seat.attendee_email,
                              subject=gettext('Your ticket to {title}').format(title=event.title), text=text, stream="events",
                              audience="requester", feature="", persist_body=False, address_owner=False)
    record(actor, "event.seat_invited", makerspace=space, target=seat.order,
           meta={"order_id": seat.order_id, "seat_id": seat.pk, "reminder": chase})
    return True


def _locked_order(order_id, member):
    order = EventOrder.objects.select_for_update().filter(pk=order_id, buyer=member).first()
    if order is None:
        from rest_framework.exceptions import NotFound
        raise NotFound(gettext("Order not found."))
    return order


@transaction.atomic
def assign_attendees(order, *, member, assignments):
    """The buyer names (or renames) the people for unclaimed seats: `{seat_id: email}`."""
    from django.core.validators import validate_email
    order = _locked_order(order.pk, member)
    if order.status not in (EventOrder.Status.PENDING, EventOrder.Status.PAID):
        raise OrderRefused("order_not_payable", "This order is closed.")
    seats = {seat.pk: seat for seat in order.seats.select_for_update().filter(status=EventOrderSeat.Status.UNCLAIMED)}
    changed = []
    for seat_id, email in assignments.items():
        seat = seats.get(int(seat_id))
        if seat is None:
            raise OrderRefused("claim_invalid", "That seat cannot be changed.", seat_id=seat_id)
        email = (email or "").strip().lower()
        if email:
            validate_email(email)
        seat.attendee_email = email
        seat.claim_token_digest = secrets.token_hex(32)  # any earlier link stops working
        seat.invited_at = seat.reminded_at = None
        seat.save(update_fields=["attendee_email", "claim_token_digest", "invited_at", "reminded_at"])
        changed.append(seat)
    record(member, "event.order_attendees_updated", makerspace=order.makerspace, target=order,
           meta={"order_id": order.pk, "seats": [seat.pk for seat in changed]})
    if order.status == EventOrder.Status.PAID:
        for seat in changed:
            send_invite(seat, actor=member)
    return order


@transaction.atomic
def chase(order, *, member):
    """Re-send the claim link to every named, unclaimed seat (once a day per seat)."""
    order = _locked_order(order.pk, member)
    if order.status != EventOrder.Status.PAID:
        raise OrderRefused("order_not_payable", "Only a paid order's seats can be claimed.")
    now, sent = timezone.now(), 0
    for seat in order.seats.select_for_update().filter(status=EventOrderSeat.Status.UNCLAIMED).exclude(
            attendee_email=""):
        last = seat.reminded_at or seat.invited_at
        if last and last > now - CHASE_COOLDOWN:
            continue
        sent += bool(send_invite(seat, actor=member, chase=True))
    return sent
