"""Shared event admission fence and registration row lock order."""

from .models import EventRegistration
from .exceptions import EventInvalidTransition

def _boundary():
    # Imported lazily so services.py can retain the established public import boundary.
    from apps.events import services

    return services


def _fence(event):
    from .organization_audience import AUDIENCE, lock_admission_sources
    lock_admission_sources(event, event.registrations.values_list("member_id", flat=True))
    if event.registration_audience != AUDIENCE:
        from apps.makerspaces.models import Makerspace
        event.makerspace = Makerspace.objects.select_for_update().get(pk=event.makerspace_id)


def _lock_registration(event, registration_id):
    registration = EventRegistration.objects.select_for_update().get(pk=registration_id)
    if registration.event_id != event.pk:
        raise EventInvalidTransition("Registration does not belong to this event.")
    registration.event = event
    return registration


