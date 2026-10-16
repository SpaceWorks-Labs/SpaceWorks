"""Lifecycle notification adapter for events, series and registrations.

Two paths per notice, never mixed:

- staff ROOMS (Telegram/Slack/Mattermost/Discord/webhook) and the staff matrix inbox/push stay
  on the legacy lifecycle dispatcher with the STAFF summary only -- no personal email and no
  owner content ever rides that payload any more;
- PERSONAL delivery is a source-backed envelope per account (`notification_envelopes`),
  written in the caller's domain transaction and delivered on commit through each person's
  selected, verified channels (email, in-app, push, Telegram, Slack, Mattermost, Discord,
  WhatsApp). Staff, per-event delegates and the registration owner get separate envelopes.
"""

import logging

from django.db import transaction

from apps.events.models import Event, EventRegistration
from apps.integrations.email_templates import render
from apps.integrations.email_templates_fablab import events_context
from apps.integrations.email_templates_registry_fablab_defaults import (
    EVENTS_REQUESTER_BODIES,
)
from apps.integrations.email_templates_registry_fablab import EVENTS_KEYS
from apps.integrations.notify import LifecyclePayload, notify_lifecycle
from apps.makerspaces.servability import servable_q
from apps.organizations.models import OrganizationMakerspace

from . import notification_envelopes as envelopes

logger = logging.getLogger(__name__)

# Kept in step with notification_catalog and the email template registry.
EVENT_NOTIFICATION_EVENTS = frozenset(EVENTS_KEYS)


def _rooms(event_id, makerspace, event_name, registration_id, *, sync):
    def build():
        event = Event.objects.select_related("makerspace").get(pk=event_id)
        registration = (EventRegistration.objects.get(pk=registration_id, event=event)
                        if registration_id is not None else None)
        context = events_context(event, event_name, registration,
                                 next_steps=EVENTS_REQUESTER_BODIES.get(event_name, ""))
        staff = render(makerspace, "events", "staff", event_name, context)
        return LifecyclePayload(
            text=staff["text_body"], context=context,
            data={"event_id": event.pk, "series_id": event.series_id,
                  "registration_id": registration.pk if registration else None},
        )

    return notify_lifecycle(makerspace, feature="events", event=event_name, build=build, sync=sync)


def _guarded(label, function, *args):
    """A notification failure never aborts or poisons the caller's domain transaction."""
    try:
        with transaction.atomic():
            return function(*args)
    except Exception:
        logger.warning(label, extra={"function": function.__name__})
        return None


def _organizer_spaces(event_id, venue_id):
    # is_active on the organization is a KILL SWITCH: it confers no organizer authority, so
    # it must stop this fan-out too -- registration notices carry the registrant's name.
    # Unservable and hard-hidden makerspaces are excluded for the same reason they are
    # excluded from organization-derived authority.
    return (OrganizationMakerspace.objects.filter(
        servable_q("makerspace"), organization__organized_events__event_id=event_id,
        organization__is_active=True, makerspace__superadmin_access_enabled=True,
    ).exclude(makerspace_id=venue_id).select_related("makerspace").order_by("makerspace_id").distinct())


def notify_event_lifecycle(event_obj, event_name, registration_id=None, *, sync=False):
    event_id, venue = event_obj.pk, event_obj.makerspace
    intent = envelopes.new_intent()
    event = Event.objects.select_related("makerspace", "series").get(pk=event_id)
    registration = (EventRegistration.objects.select_related("member", "registered_via_makerspace")
                    .filter(pk=registration_id, event=event).first() if registration_id is not None else None)
    try:
        venue_result = _rooms(event_id, venue, event_name, registration_id, sync=sync)
    except Exception:
        logger.warning("event_venue_notification_failed", extra={"event_id": event_id, "makerspace_id": venue.pk})
        venue_result = None
    _guarded("event_staff_envelopes_failed", envelopes.staff_envelopes, venue, event, event_name, registration, intent)
    if registration is not None:
        _guarded("event_owner_envelope_failed", envelopes.owner_envelope, event, event_name, registration, intent)
    else:
        _guarded("event_owner_fanout_failed", envelopes.owner_fanout, [event], event_name, intent)
    if registration_id is None:
        return venue_result
    delivered_to = {venue.pk}
    for link in _organizer_spaces(event_id, venue.pk):
        if link.makerspace_id in delivered_to:
            continue
        delivered_to.add(link.makerspace_id)
        try:
            _rooms(event_id, link.makerspace, event_name, registration_id, sync=sync)
        except Exception:
            # notify_lifecycle is already fail-safe; keep this boundary so one organizer
            # cannot suppress the remaining spaces.
            logger.warning("event_organizer_notification_failed",
                           extra={"event_id": event_id, "makerspace_id": link.makerspace_id})
        _guarded("event_organizer_envelopes_failed", envelopes.staff_envelopes,
                 link.makerspace, event, event_name, registration, intent)
    return venue_result


def notify_series_lifecycle(series_obj, event_name, *, sync=False):
    """Send one bounded lifecycle message for a series, never one per occurrence."""
    occurrence = series_obj.occurrences.select_related("makerspace").order_by("starts_at", "pk").first()
    if occurrence is None:
        return None
    intent = envelopes.new_intent()
    try:
        result = _rooms(occurrence.pk, series_obj.makerspace, event_name, None, sync=sync)
    except Exception:
        logger.warning("event_series_notification_failed",
                       extra={"series_id": series_obj.pk, "makerspace_id": series_obj.makerspace_id})
        result = None
    _guarded("event_series_staff_envelopes_failed", envelopes.staff_envelopes,
             series_obj.makerspace, occurrence, event_name, None, intent)
    if event_name != "series_generation_failed":  # staff-only, never an owner notice
        _guarded("event_series_owner_fanout_failed", envelopes.owner_fanout,
                 list(series_obj.occurrences.all()), event_name, intent)
    return result
