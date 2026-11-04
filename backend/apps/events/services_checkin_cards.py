"""Scan a card at the event door (#132, Q-I10): find the person's confirmed registration.

Accepted codes: this event's ID card check link, a member card (desk QR or check link)
of the host space, or a programme card check link. The scan IDENTIFIES the person for
the door staff, who remain the actor; it never signs anyone in. One confirmed
registration -> it can be checked in straight away through the normal check-in
service (same audit and evidence as a ticket scan); none or several -> a list to pick.
"""
from rest_framework.exceptions import NotFound

from .models import EventRegistration


def person_for(event, payload, actor):
    from apps.card_designs.scan import live_holder, person_for as member_person
    kind, card = live_holder(event.makerspace_id, payload)
    if kind == "event_card" and card is not None and card.event_id == event.pk and card.status == "active":
        return card.person_id, card.registration_id
    if kind in ("programme_card",) and card is not None:
        return card.user_id, None
    account_id, _member_card = member_person(event.makerspace, payload, actor=actor)
    return account_id, None


def candidates(event, payload, actor):
    account_id, registration_id = person_for(event, payload, actor)
    if account_id is None and registration_id is None:
        raise NotFound()
    rows = EventRegistration.objects.filter(event=event)
    rows = rows.filter(pk=registration_id) if registration_id else rows.filter(member_id=account_id)
    rows = list(rows.order_by("pk"))
    if not rows:
        raise NotFound()
    return rows


def check_in(event, registration, actor):
    from .models_attendance import EventCheckInEvent
    from .services_checkin import mark_attended_with_event
    return mark_attended_with_event(registration, actor=actor, source=EventCheckInEvent.Source.QR)
