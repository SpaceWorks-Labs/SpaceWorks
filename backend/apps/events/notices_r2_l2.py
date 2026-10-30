"""Member notices added by lane L2 (G7): removal after the undo window, ticket re-send.

* **Removed by the organiser.** A staff removal can be undone for five minutes
  (`operations.cancellation_restore.RESTORE_WINDOW`). The member hears about it only once
  that window has passed and the registration is STILL cancelled by that same removal:
  the envelope is deferred to the window's end and its live source check compares the
  cancellation timestamp, so an undone removal sends nothing.
* **Email change re-sends the ticket.** When an account verifies a new email address,
  each upcoming confirmed ticket registered under a different address is sent again, so
  it reaches the new mailbox. One notice
  per registration per address (the dedup key carries an address hash, never the address).
"""

import logging
from hashlib import sha256

from django.db import transaction
from django.utils import timezone

from apps.integrations.notification_links import local_link
from apps.integrations.notification_outbox import emit

logger = logging.getLogger(__name__)
REMOVAL_SOURCE = "events.removal"
TICKET_SOURCE = "events.ticket_resend"


def staff_removal(registration):
    """True when the latest cancellation was made by someone other than the member."""
    from apps.audit.models import AuditLog
    row = AuditLog.objects.filter(
        makerspace_id=registration.event.makerspace_id, action="event.registration_cancelled",
        target_type="events.eventregistration", target_id=str(registration.pk),
    ).order_by("-created_at", "-pk").values_list("actor_id", flat=True).first()
    return bool(row) and row != registration.member_id


def removal_envelope(event, registration, space):
    from apps.operations.cancellation_restore import RESTORE_WINDOW
    if registration.cancelled_at is None:
        return None
    stamp = registration.cancelled_at.isoformat()
    return emit(
        makerspace=space, recipient=registration.member, feature="events", stream="events",
        event="registration_removed", audience="requester",
        dedup_key=f"ev:removal:{registration.pk}:{sha256(stamp.encode()).hexdigest()[:32]}",
        source_kind=REMOVAL_SOURCE, source_id=f"r{registration.pk}", revision=stamp[:64], subject=registration,
        context={"event_id": event.pk, "registration_id": registration.pk, "cancelled_at": stamp},
        rendered={"subject": f"Your place at {event.title} was removed",
                  "text": f"The organisers removed your registration for {event.title}. "
                          "If this looks wrong, reply to the organisers or contact the space.",
                  "html": "", "link": local_link(space, "member", "events")},
        timing_policy="deferred", available_at=registration.cancelled_at + RESTORE_WINDOW,
    )


def removal_eligible(envelope):
    from .models import EventRegistration
    from .notification_envelopes import _owner_allowed
    row = EventRegistration.objects.select_related("event__makerspace").filter(
        pk=envelope.context.get("registration_id"), event_id=envelope.context.get("event_id")).first()
    return bool(row and row.status == EventRegistration.Status.CANCELLED and row.cancelled_at
                and row.cancelled_at.isoformat() == envelope.context.get("cancelled_at")
                and row.member_id == envelope.recipient_id and envelope.audience == "requester"
                and (row.registered_via_makerspace_id or row.event.makerspace_id) == envelope.makerspace_id
                and _owner_allowed(envelope.makerspace, "registration_removed"))


CONFIRMATION_EVENTS = frozenset({"registration_created", "registration_approved",
                                 "registration_promoted", "registration_restored"})


def join_url_value(event_name, registration):
    if event_name not in CONFIRMATION_EVENTS:
        return ""
    from .online_delivery import join_url_for
    return join_url_for(registration) or ""


def with_join_url(rendered, event_name, registration):
    """Confirmation email carries the join link for online/hybrid events (L1 seam).

    `online_delivery.join_url_for` releases it to confirmed registrants only, while the
    space has `events.online_delivery` on. It lives in the encrypted message body only,
    never in envelope context or audit metadata.
    """
    if event_name not in CONFIRMATION_EVENTS:
        return rendered
    from .online_delivery import join_url_for
    url = join_url_for(registration)
    if not url or url in rendered.get("text", ""):
        return rendered
    import html
    rendered = dict(rendered)
    rendered["text"] = rendered.get("text", "").rstrip() + f"\n\nJoin online: {url}\n"
    if rendered.get("html"):
        rendered["html"] += (f'<p>Join online: <a href="{html.escape(url, quote=True)}">'
                             f"{html.escape(url)}</a></p>")
    return rendered


def _address_hash(user):
    return sha256((user.email or "").strip().lower().encode()).hexdigest()


def _upcoming(user):
    from .models import Event, EventRegistration
    return (EventRegistration.objects.filter(
        member=user, status=EventRegistration.Status.REGISTERED, event__status=Event.Status.PUBLISHED,
        event__starts_at__gt=timezone.now()).select_related("event__makerspace", "registered_via_makerspace"))


def resend_tickets(user):
    from apps.integrations.recipients_owners import eligible_owner
    from apps.makerspaces.platform import module_enabled
    from .notification_envelopes import _owner_allowed
    digest = _address_hash(user)
    sent = 0
    for registration in _upcoming(user)[:50]:
        space = registration.registered_via_makerspace or registration.event.makerspace
        if (not module_enabled(registration.event.makerspace, "events") or not eligible_owner(space, user.pk)
                or not _owner_allowed(space, "ticket_resent")):
            continue
        if (registration.email or "").strip().lower() == (user.email or "").strip().lower():
            continue  # the ticket already went to this address
        event = registration.event
        emit(makerspace=space, recipient=user, feature="events", stream="events", event="ticket_resent",
             audience="requester", dedup_key=f"ev:ticket-resend:{registration.pk}:{digest[:32]}",
             source_kind=TICKET_SOURCE, source_id=f"r{registration.pk}", revision=digest[:64], subject=registration,
             context={"event_id": event.pk, "registration_id": registration.pk, "address_sha256": digest},
             rendered={"subject": f"Your ticket for {event.title}",
                       "text": f"Your email address changed, so here is your ticket for {event.title} again. "
                               "Show it at the door.",
                       "html": "", "link": local_link(space, "member", f"events/{registration.pk}/ticket")})
        sent += 1
    return sent


def ticket_eligible(envelope):
    from apps.accounts.models import User
    user = User.objects.filter(pk=envelope.recipient_id).first()
    if user is None or not user.email_verified_at or _address_hash(user) != envelope.context.get("address_sha256"):
        return False
    return _upcoming(user).filter(pk=envelope.context.get("registration_id"),
                                  event_id=envelope.context.get("event_id")).exists()


def on_audit_saved(sender, instance, created=False, **kwargs):
    """A verified (changed) email is recorded as `member.email_verified`; re-send after commit.

    Verification writes with a queryset update, so the audit row is the one durable signal
    that a NEW address was proven. Fail-safe: a delivery problem never touches that flow.
    """
    if not created or instance.action != "member.email_verified" or not instance.actor_id:
        return
    user_id = instance.actor_id

    def send():
        from apps.accounts.models import User
        try:
            user = User.objects.filter(pk=user_id).first()
            if user is not None:
                resend_tickets(user)
        except Exception:
            logger.warning("event_ticket_resend_failed", extra={"user_id": user_id})
    transaction.on_commit(send)


def connect():
    from django.db.models.signals import post_save
    from apps.audit.models import AuditLog
    post_save.connect(on_audit_saved, sender=AuditLog, dispatch_uid="events_ticket_resend_on_verify")
