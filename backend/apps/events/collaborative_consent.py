"""Batch an owned-row consent advisory without exposing participants or admission proofs."""

from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership
from .host_waivers import has_current_host_consent
from .models import Event, EventRegistration


def consent_repair_event_ids(events, user, waivers):
    registrations = {row.event_id: row for row in EventRegistration.objects.filter(
        event_id__in=[event.pk for event in events], member=user,
        status__in=(EventRegistration.Status.REGISTERED, EventRegistration.Status.WAITLISTED,
                    EventRegistration.Status.PENDING_APPROVAL),
    )}
    memberships = {row.makerspace_id: row for row in MakerspaceMembership.objects.filter(
        makerspace_id__in=waivers, user=user, status="active",
    )}
    now = timezone.now()
    return {event.pk for event in events
            if event.pk in registrations and event.status == Event.Status.PUBLISHED and now < event.ends_at
            and not has_current_host_consent(waivers.get(event.makerspace_id),
                                             memberships.get(event.makerspace_id), registrations[event.pk])}
