"""The calendar invite and ticket PDF on registration confirmation emails (#169, L3 contract).

The owner's confirmation email (`events.lifecycle`, audience requester) gets, at send time:

* an `.ics` invite -- METHOD:PUBLISH with the stable UID
  `event-<event uid>-r<registration id>@spaceworks` and SEQUENCE = event sequence +
  registration sequence, so a change re-sends a higher sequence; a cancellation of the
  registration or the event sends METHOD:CANCEL;
* the ticket PDF, as a typed email-only attachment (`events.ticket`) rendered by
  `id_cards_tickets.render_ticket` when `events.ticket_designs` is on;
* "Add to Google Calendar" / "Add to Outlook" links in the body.

Only public event fields ride the invite and the links: never the online join link,
which stays in the confirmed registrant's message body (`online_delivery` rules).
"""

from django.utils.translation import gettext
from apps.makerspaces.calendar_invites import calendar_links, invite_ics

CONFIRMED = frozenset({"registration_created", "registration_approved", "registration_promoted",
                       "registration_restored", "registration_updated"})
CANCELLED = frozenset({"registration_cancelled", "cancelled", "registration_removed"})
TICKET_SOURCE = "events.ticket"


def uid(registration):
    return f"event-{registration.event.calendar_uid}-r{registration.pk}@spaceworks"


def _public_description(event):
    return (event.description or "")[:2000]


def invite_bytes(registration, *, cancel=False):
    from .calendar_alarms import add_member_alarms
    event = registration.event
    cancel = cancel or event.status == event.Status.CANCELLED or registration.status in ("cancelled", "rejected")
    return invite_ics(
        uid=uid(registration), title=event.title, starts_at=event.starts_at, ends_at=event.ends_at,
        sequence=event.calendar_sequence + registration.calendar_sequence,
        updated_at=max(event.calendar_updated_at, registration.calendar_updated_at), cancel=cancel,
        tentative=registration.status in ("pending_approval", "waitlisted"),
        description=_public_description(event), location=event.location or "",
        alarms=lambda entry: add_member_alarms(entry, event.makerspace, event.title))


def links(registration):
    event = registration.event
    return calendar_links(title=event.title, starts_at=event.starts_at, ends_at=event.ends_at,
                          description=_public_description(event)[:500], location=event.location or "")


def with_links(rendered, event_name, registration):
    """Owner confirmation copy gains the two "add to calendar" links (no join link inside)."""
    from apps.makerspaces.calendar_invites import with_calendar_links
    if registration is None or event_name not in CONFIRMED or registration.status not in ("registered",):
        return rendered
    return with_calendar_links(rendered, links(registration))


def _registration(envelope):
    from .models import EventRegistration
    return (EventRegistration.objects.select_related("event__makerspace")
            .filter(pk=envelope.context.get("registration_id"), member_id=envelope.recipient_id).first())


def attachments(envelope):
    """Typed and inline attachments for one owner envelope; () when none apply."""
    from apps.integrations.inline_attachments import InlineAttachment
    if envelope.audience != "requester" or envelope.event not in CONFIRMED | CANCELLED:
        return ()
    registration = _registration(envelope)
    if registration is None:
        return ()
    cancel = envelope.event in CANCELLED
    items = [InlineAttachment(f"event-{registration.event_id}.ics", invite_bytes(registration, cancel=cancel),
                              f"text/calendar; charset=utf-8; method={'CANCEL' if cancel else 'PUBLISH'}")]
    if not cancel and registration.status == "registered" and _tickets_on(registration):
        from apps.integrations.notification_attachment_sources import AttachmentReference
        items.append(AttachmentReference(TICKET_SOURCE, registration.pk, "ticket", revision(registration)))
    return tuple(items)


def _tickets_on(registration):
    from apps.card_designs.switches import domain_on
    return domain_on(registration.event.makerspace, "event_ticket")


def revision(registration):
    return str(registration.event.calendar_sequence + registration.calendar_sequence)


def authorize(reference, *, makerspace_id, recipient_id):
    from apps.integrations.notification_attachment_sources import DocumentDeliveryError
    from .models import EventRegistration
    row = EventRegistration.objects.select_related("event__makerspace").filter(pk=reference.document_id).first()
    space = row and (row.registered_via_makerspace_id or row.event.makerspace_id)
    if (row is None or row.member_id != recipient_id or makerspace_id not in (space, row.event.makerspace_id)
            or row.status not in ("registered", "attended") or not _tickets_on(row)
            or revision(row) != reference.revision):
        raise DocumentDeliveryError("document_not_authorized")
    return row


def render(reference, *, makerspace_id, recipient_id):
    from apps.integrations.notification_attachment_sources import DocumentDeliveryError
    from .id_cards_tickets import render_ticket
    row = authorize(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
    try:
        filename, data, _content_type = render_ticket(row, fmt="pdf")
    except Exception:
        raise DocumentDeliveryError("document_render_failed") from None
    return filename, data, "application/pdf"


def register():
    from apps.integrations.inline_attachments import register_confirmation_attachments
    from apps.integrations.notification_attachment_sources import AttachmentSource, register_source
    register_source(TICKET_SOURCE, AttachmentSource(lambda envelope: (), authorize, render, None,
                                                    lambda row: (row.event.makerspace_id,)))
    register_confirmation_attachments("events.lifecycle", attachments)
    register_confirmation_attachments("events.removal", attachments)
    register_updates()


UPDATE_SOURCE = "events.invite_update"


def event_changed(event):
    """Lane L6 hook from `services_calendar.calendar_event_changed`: re-send updated invites."""
    from django.db import transaction
    if event.status != event.Status.PUBLISHED:
        return
    event_id, sequence = event.pk, event.calendar_sequence

    def enqueue():
        from .tasks_invites import send_invite_updates_task
        try:
            send_invite_updates_task.delay(event_id, sequence)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("event_invite_update_enqueue_failed", extra={"event_id": event_id})

    transaction.on_commit(enqueue)


def update_envelope(registration):
    from apps.integrations.notification_links import local_link
    from apps.integrations.notification_outbox import emit
    from apps.integrations.recipients_owners import eligible_owner
    event = registration.event
    space = registration.registered_via_makerspace or event.makerspace
    if not registration.member_id or not eligible_owner(space, registration.member_id):
        return None
    stamp = revision(registration)
    rendered = lambda: with_links(  # noqa: E731 - built in the recipient's language by emit()
        {"subject": gettext("Updated: %(title)s") % {"title": event.title},
         "text": gettext("The details of %(title)s changed. The attached invite updates your "
                         "calendar entry.") % {"title": event.title}, "html": "",
         "link": local_link(space, "member", f"events/{registration.pk}/ticket")},
        "registration_updated", registration)
    return emit(makerspace=space, recipient=registration.member, feature="events", stream="events",
                event="registration_updated", audience="requester",
                dedup_key=f"ev:invite:{registration.pk}:{stamp}", source_kind=UPDATE_SOURCE,
                source_id=f"r{registration.pk}", revision=stamp, subject=registration,
                context={"event_id": event.pk, "registration_id": registration.pk, "sequence": stamp},
                rendered=rendered)


def update_eligible(envelope):
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    row = _registration(envelope)
    return bool(row and envelope.audience == "requester" and row.status == "registered"
                and row.event.status == row.event.Status.PUBLISHED and revision(row) == envelope.revision
                and is_servable(row.event.makerspace) and module_enabled(row.event.makerspace, "events")
                and (row.registered_via_makerspace_id or row.event.makerspace_id) == envelope.makerspace_id)


def register_updates():
    from apps.integrations.inline_attachments import register_confirmation_attachments
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(UPDATE_SOURCE, NotificationSource(update_eligible))
    register_confirmation_attachments(UPDATE_SOURCE, attachments)
