"""Ticket transfers (release 2 L6, G32): hand a confirmed ticket to someone else.

Allowed only when the space has `events.transfers` on, the organiser allows transfers on
this event, the registration is confirmed and the transfer cutoff has not passed
(`transfer_not_allowed` otherwise). The sender names an email; the recipient gets a
single-use link (stored as a SHA-256 digest), signs in with that verified address and
accepts. Then, under the event write boundary, the registration moves to the recipient:
contact details from their account, a rotated check-in credential (the old QR stops
working), the old event ID card revoked and a new one issued to them, and any live
certificate revoked. The money stays with whoever paid; nobody is registered without
an account.
"""

from django.utils.translation import gettext
import secrets
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from apps.audit.services import record

from .models import EventRegistration, EventTicketTransfer
from .orders_attendees import token_digest
from .orders_errors import OrderRefused
from .services_write_boundary import event_write

OFFER_DAYS = 7


def transfer_window_open(registration, settings_row, *, flag="transfers_allowed"):
    event = registration.event
    cutoff = event.starts_at - timedelta(hours=settings_row.transfer_cutoff_hours or 0)
    return bool(getattr(settings_row, flag) and event.status == event.Status.PUBLISHED
                and registration.status == EventRegistration.Status.REGISTERED and timezone.now() < cutoff)


def require_transfers(registration, *, flag="transfers_allowed"):
    from .feature_gates import require_feature
    from .orders_quote import sales_settings
    require_feature(registration.event, "events.transfers")
    if not transfer_window_open(registration, sales_settings(registration.event), flag=flag):
        raise OrderRefused("transfer_not_allowed", "This ticket cannot be transferred or changed now.")


def accept_url(token):
    base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return f"{base}/member/ticket-transfers/{token}"


@event_write
def offer_transfer(registration, *, actor, to_email):
    from django.core.validators import validate_email
    row = EventRegistration.objects.select_for_update().select_related("event__makerspace").get(pk=registration.pk)
    if row.member_id != actor.pk:
        raise OrderRefused("transfer_not_allowed", "Only the ticket holder can transfer it.")
    require_transfers(row)
    email = (to_email or "").strip().lower()
    validate_email(email)
    if email == (actor.email or "").strip().lower():
        raise OrderRefused("transfer_not_allowed", "Choose someone else to receive the ticket.")
    now = timezone.now()
    EventTicketTransfer.objects.select_for_update().filter(registration=row, status="pending").update(
        status=EventTicketTransfer.Status.CANCELLED, decided_at=now)
    token = secrets.token_urlsafe(32)
    transfer = EventTicketTransfer.objects.create(
        makerspace=row.event.makerspace, registration=row, from_member=actor, to_email=email,
        token_digest=token_digest(token), expires_at=min(now + timedelta(days=OFFER_DAYS), row.event.starts_at))
    record(actor, "event.ticket_transfer_offered", makerspace=row.event.makerspace, target=row,
           meta={"registration_id": row.pk, "transfer_id": transfer.pk})
    send_offer(transfer, token)
    return transfer


def send_offer(transfer, token):
    from apps.operations.notifications_p2 import direct_mail_unless_routed
    event, space = transfer.registration.event, transfer.makerspace
    sender = transfer.from_member.display_name or transfer.from_member.get_full_name() or "Someone"
    text = (f"{sender} wants to pass their ticket for {event.title} at {space.name} to you.\n"
            f"Sign in or create your account with this email address, then accept it here:\n"
            f"{accept_url(token)}\nThe offer ends on {timezone.localtime(transfer.expires_at):%d %b %Y}.\n")
    direct_mail_unless_routed(space=space, source_kind="events.ticket_transfer", row=transfer,
                              revision=transfer.token_digest[:16], event="ticket_transfer_received", owner=None,
                              to_email=transfer.to_email, subject=gettext('A ticket to {title} for you').format(title=event.title), text=text,
                              stream="events", audience="requester", feature="", persist_body=False,
                              address_owner=False)


def find_offer(token):
    transfer = (EventTicketTransfer.objects.select_related("registration__event__makerspace", "from_member")
                .filter(token_digest=token_digest(token), status="pending", expires_at__gt=timezone.now()).first()
                if token and len(str(token)) <= 128 else None)
    if transfer is None:
        raise OrderRefused("claim_invalid", "This transfer link is not valid any more.")
    return transfer


def accept(token, *, user):
    transfer = find_offer(token)
    email = (user.email or "").strip().lower()
    if email != transfer.to_email or not getattr(user, "email_verified_at", None):
        raise OrderRefused("claim_email_mismatch", "Sign in with the verified email address the ticket was sent to.")
    return _accept(transfer.registration, member=user, actor=user, transfer_id=transfer.pk)


@event_write
def _accept(registration, *, member, actor, transfer_id):
    from .registration_access import require_registration_access
    transfer = EventTicketTransfer.objects.select_for_update().get(pk=transfer_id, registration_id=registration.pk)
    row = EventRegistration.objects.select_for_update().select_related("event__makerspace").get(pk=registration.pk)
    if transfer.status != "pending" or row.member_id != transfer.from_member_id:
        raise OrderRefused("claim_invalid", "This transfer is no longer open.")
    require_transfers(row)
    event = row.event
    if event.registrations.filter(member=member, status__in=("pending_approval", "registered", "waitlisted",
                                                             "attended")).exists():
        raise OrderRefused("already_registered", "You already have a place at this event.")
    require_registration_access(event, member)
    _move(row, member)
    rotate_credentials(event, row, actor=actor)
    transfer.status, transfer.accepted_by, transfer.decided_at = "accepted", member, timezone.now()
    transfer.save(update_fields=["status", "accepted_by", "decided_at"])
    record(actor, "event.ticket_transferred", makerspace=event.makerspace, target=row,
           meta={"registration_id": row.pk, "transfer_id": transfer.pk, "from_member_id": transfer.from_member_id})
    return row


def _move(row, member):
    from .services_calendar import calendar_registration_changed
    row.member = member
    row.name = member.display_name or member.get_full_name() or member.username
    row.email = (member.email or "").strip().lower()
    row.phone = member.phone or row.phone
    fields = ["member", "name", "email", "phone", "version"]
    if settings.PII_ENCRYPTION_ENABLED:
        from apps.encryption.blind_index import active_generation, event_email_hash
        generation = active_generation()
        row.email_hash_generation = generation
        row.email_exact_hash = event_email_hash(row.email, generation=generation.generation,
                                                makerspace_id=row.event.makerspace_id, event_id=row.event_id)
        fields += ["email_hash_generation", "email_exact_hash"]
    row.version += 1
    row.save(update_fields=fields)
    seat = getattr(row, "order_seat", None)
    if seat is not None:
        seat.attendee_email = row.email
        seat.save(update_fields=["attendee_email"])
    calendar_registration_changed(row)


def rotate_credentials(event, row, *, actor):
    """The old holder's QR, ID card and certificates stop working; the new holder's start."""
    if row.credential_mode == "v2":
        from .credentials.preparation import prepared_issue
        from .credentials.workflow import issue_locked
        issue_locked(event, row, actor=actor, rotate=True, prepared=prepared_issue(event.pk, row.pk))
    elif row.credential_mode == "legacy":
        row.checkin_token = uuid4()
        row.save(update_fields=["checkin_token"])
        record(actor, "event.credential_revoked", makerspace=event.makerspace, target=row,
               meta={"registration_id": row.pk, "reason": "transferred"})
    from .models import EventIdCard
    from .id_cards import _revoke_locked, reconcile_event
    for card in EventIdCard.objects.select_for_update().filter(registration=row, status="active"):
        _revoke_locked(actor, card, "Ticket transferred.")
        from apps.card_designs.lifecycle import on_revoke
        on_revoke("event_card", card)
    reconcile_event(event.pk, actor)
    from .models_certificates import EventAttendanceCertificate
    from .certificates.lifecycle import revoke_locked
    for certificate in EventAttendanceCertificate.objects.select_for_update().filter(registration=row,
                                                                                     status="active"):
        revoke_locked(event, certificate, actor=actor, reason="staff_revoked")
