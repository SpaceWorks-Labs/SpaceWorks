"""Source-backed personal envelopes for event lifecycle notices (Phase 2 adapters).

Three audiences, each a SEPARATE envelope with its own body, so a requester's wording never
reaches staff and a registrant's name never reaches an attendee:

- staff: every account `staff_user_ids_for_feature` resolves (Event/Space Manager, with the
  existing recipient selections, mutes and live re-check in the shared layer);
- event staff grants: accounts holding `manage_registrations` on THIS event or its series,
  re-checked live through `event_authority` at every send;
- owners: the registration's own account (account-only owners included; a revoked member is
  refused by `eligible_owner`).

Staff rooms are not envelopes; `notifications.py` keeps them on the legacy matrix path with
the staff summary only. That path also still writes the staff matrix inbox and native push,
so staff envelopes pre-mark those two channels as skipped instead of delivering them twice.
"""

import logging
from hashlib import sha256
from uuid import uuid4

from django.db import transaction

from apps.integrations.notification_links import local_link
from apps.integrations.email_templates import render
from apps.integrations.email_templates_fablab import events_context
from apps.integrations.email_templates_registry_fablab_defaults import EVENTS_REQUESTER_BODIES
from apps.integrations.notification_outbox import emit
from apps.hardware_requests.notification_projection import addressed_context

logger = logging.getLogger(__name__)

LIFECYCLE_SOURCE = "events.lifecycle"
GRANT_SOURCE = "events.grant_staff"
# Delivered for staff by the legacy matrix path (write_matrix_inbox + native push channel).
LEGACY_STAFF_CHANNELS = ("in_app", "native_push")
OWNER_FANOUT_STATUSES = {
    "published": ("registered", "waitlisted", "pending_approval"),
    "cancelled": ("registered", "waitlisted", "pending_approval"),
    "completed": ("registered", "attended"),
    "series_published": ("registered", "waitlisted", "pending_approval"),
    "series_cancelled": ("registered", "waitlisted", "pending_approval"),
    "series_completed": ("registered", "attended"),
}


def new_intent():
    return uuid4().hex


def lifecycle_revision(event, registration):
    """The persisted wording belongs to this resource state, not just its existence."""
    values = (event.status, event.calendar_sequence, event.updated_at,
              registration.status if registration else None,
              registration.calendar_sequence if registration else None)
    return sha256("\x1f".join(str(value) for value in values).encode()).hexdigest()


def _rendered(template, link):
    return {"subject": template["subject"], "text": template["text_body"],
            "html": template.get("html_body", ""), "link": link}


def _staff_link(space, event):
    from apps.operations.notifications_p2 import staff_link
    return staff_link(space, f"events?event={event.pk}")


def _owner_link(space, registration):
    if registration is not None and registration.status in ("registered", "attended"):
        return local_link(space, "member", f"events/{registration.pk}/ticket")
    return local_link(space, "member")


def _context(event, registration, event_name):
    # Only identifiers and enums: names, emails and bodies belong in the encrypted render.
    return {"event_id": event.pk, "registration_id": registration.pk if registration else None,
            "event_status": event.status, "notice": event_name}


def _emit(space, user, *, audience, event_name, source_kind, source_id, intent, event, registration,
          rendered, skip=()):
    from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
    version = lifecycle_revision(event, registration)
    template_context = events_context(event, event_name, registration)
    identity = f"{source_kind}:{source_id}:{event_name}:{version}:{space.pk}:{audience}:{user.pk}"
    with transaction.atomic():
        # T used random per-call keys. Reuse its already persisted source intent
        # across the upgrade; changing the key must not create a second delivery.
        existing = NotificationEnvelope.objects.filter(makerspace=space, recipient=user,
            source_kind=source_kind, source_id=str(source_id), event=event_name,
            revision=version, audience=audience).order_by("pk").first()
        envelope = emit(
            makerspace=space, recipient=user, feature="events", stream="events", event=event_name,
            audience=audience,
            dedup_key=existing.dedup_key if existing else f"ev:{sha256(identity.encode()).hexdigest()}",
            source_kind=source_kind, source_id=str(source_id), revision=version,
            subject=registration or event,
            context={**addressed_context(space, "events", event_name, audience, template_context),
                     **_context(event, registration, event_name)}, rendered=rendered,
        )
        for channel in skip:
            NotificationDelivery.objects.get_or_create(envelope=envelope, channel=channel, defaults={
                "makerspace": space, "target_key": channel, "provider": "builtin",
                "state": "skipped", "last_error": "legacy_matrix_channel"})
    return envelope


def staff_envelopes(space, event, event_name, registration, intent):
    from apps.accounts.models import User
    from apps.integrations.staff_notifications import staff_user_ids_for_feature
    context = events_context(event, event_name, registration,
                             next_steps=EVENTS_REQUESTER_BODIES.get(event_name, ""))
    rendered = _rendered(render(space, "events", "staff", event_name, context), _staff_link(space, event))
    staff_ids = staff_user_ids_for_feature(space, "events", event=event_name)
    source_id = f"r{registration.pk}" if registration else f"e{event.pk}"
    for user in User.objects.filter(pk__in=staff_ids).order_by("pk"):
        _emit(space, user, audience="staff", event_name=event_name, source_kind=LIFECYCLE_SOURCE,
              source_id=source_id, intent=intent, event=event, registration=registration,
              rendered=rendered, skip=LEGACY_STAFF_CHANNELS)
    if registration is None or space.pk != event.makerspace_id:
        return
    # Per-event delegates (door staff, registration desk) who are not tenant staff.
    from .grant_recipients import registration_grantees
    for user in registration_grantees(event).exclude(pk__in=staff_ids):
        _emit(space, user, audience="member", event_name=event_name, source_kind=GRANT_SOURCE,
              source_id=source_id, intent=intent, event=event, registration=registration, rendered=rendered)


def _owner_allowed(space, event_name):
    from apps.integrations import notification_rules
    from apps.integrations.recipients import has_selection, requester_selected
    if has_selection(space, "events", event_name) and not requester_selected(space, "events", event_name):
        return False
    return not notification_rules.is_requester_muted(space, "events", event_name)


def owner_envelope(event, event_name, registration, intent):
    from apps.integrations.recipients_owners import eligible_owner
    if registration is None or not registration.member_id:
        return None
    space = registration.registered_via_makerspace or event.makerspace
    from .notices_r2_l2 import join_url_value, removal_envelope, staff_removal, with_join_url
    if event_name == "registration_cancelled" and staff_removal(registration):
        # Undoable for five minutes: the member hears once the removal has stuck (G7).
        if not eligible_owner(space, registration.member_id):
            return None
        return removal_envelope(event, registration, space)
    if not _owner_allowed(space, event_name) or not eligible_owner(space, registration.member_id):
        return None
    context = events_context(event, event_name, registration,
                             next_steps=EVENTS_REQUESTER_BODIES.get(event_name, ""))
    # `{{ join_url }}` for custom templates; render-only, never stored in envelope context.
    context["join_url"] = join_url_value(event_name, registration)
    rendered = with_join_url(_rendered(render(space, "events", "requester", event_name, context),
                                       _owner_link(space, registration)), event_name, registration)
    from .registration_invites import with_links  # #169 (lane L6): add-to-calendar links, no join link
    rendered = with_links(rendered, event_name, registration)
    return _emit(space, registration.member, audience="requester", event_name=event_name,
                 source_kind=LIFECYCLE_SOURCE, source_id=f"r{registration.pk}", intent=intent,
                 event=event, registration=registration, rendered=rendered)


def owner_fanout(events, event_name, intent):
    """One notice per live registration owner of these occurrences (event/series lifecycle)."""
    from .models import EventRegistration
    statuses = OWNER_FANOUT_STATUSES.get(event_name)
    if not statuses:
        return 0
    seen, sent = set(), 0
    rows = (EventRegistration.objects.filter(event__in=events, status__in=statuses, member__isnull=False)
            .select_related("event__makerspace", "member", "registered_via_makerspace").order_by("pk"))
    for registration in rows.iterator(chunk_size=200):
        if registration.member_id in seen:
            continue
        seen.add(registration.member_id)
        try:
            if owner_envelope(registration.event, event_name, registration, intent) is not None:
                sent += 1
        except Exception:
            # One owner's bad row (e.g. a template error) cannot starve the rest.
            logger.warning("event_owner_fanout_failed", extra={"registration_id": registration.pk})
    return sent


CERTIFICATE_COPY = {
    "certificate_ready": ("Your {noun} is ready", "Your {noun} for {title} is ready to download."),
    "certificate_revoked": ("Your {noun} was withdrawn",
                            "The {noun} for {title} was withdrawn. Contact the organizers if this looks wrong."),
}


def certificate_copy(certificate, event_name, title):
    """Subject and text naming the real certificate kind (winner, mentor thank-you, …)."""
    from apps.events.certificates.merge import kind_noun
    subject, text = CERTIFICATE_COPY[event_name]
    noun = kind_noun(getattr(certificate, "kind", "attendance"))
    return subject.format(noun=noun), text.format(noun=noun, title=title)


def certificate_envelope(certificate, event_name):
    """Navigation notice only: never the document, a bearer or another person's details."""
    from apps.integrations.recipients_owners import eligible_owner
    registration = certificate.registration
    event = registration.event
    space = registration.registered_via_makerspace or event.makerspace
    if not registration.member_id or not eligible_owner(space, registration.member_id):
        return None
    subject, text = certificate_copy(certificate, event_name, event.title)
    with transaction.atomic():
        return emit(
            makerspace=space, recipient=registration.member, feature="events", stream="events",
            event=event_name, audience="requester",
            dedup_key=f"ev:certificate:{certificate.pk}:{certificate.revision}:{event_name}",
            source_kind="events.certificate", source_id=str(certificate.pk), revision=str(certificate.revision),
            subject=certificate, context={"event_id": event.pk, "certificate_id": certificate.pk},
            rendered={"subject": subject, "text": text, "html": "",
                      "link": local_link(space, "member")},
        )
