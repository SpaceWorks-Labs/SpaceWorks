"""Event ID cards: automatic issue to confirmed registrants, revoke, role (SPEC §4.4).

Q-I8: every confirmed registrant gets a card once the event has a PUBLISHED event-card
design. Issuance reconciles rather than hooking registration internals: on publish,
from the "issue now" action, and every 15 minutes (`reconcile_event`). A registration
that is no longer confirmed loses its live card (revoked, reason "registration ended").
Valid until the event's end + 1 day (Q-I6). Never charged (C-20).
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .models import Event, EventIdCard, EventRegistration

CONFIRMED = (EventRegistration.Status.REGISTERED, EventRegistration.Status.ATTENDED)
VALID_AFTER_END = timedelta(days=1)


def valid_until(event):
    return event.ends_at + VALID_AFTER_END


def has_published_design(event):
    from apps.card_designs.models import CardDesign
    return CardDesign.objects.filter(event=event, domain="event_card", published_document__isnull=False).exists() or \
        CardDesign.objects.filter(makerspace_id=event.makerspace_id, domain="event_card", event__isnull=True,
                                  published_document__isnull=False).exists()


def _role(event, registration):
    from .contributions.crew_reads import crew_labels
    crew = crew_labels(event, [registration.pk]).get(registration.pk)
    if crew is not None:
        return EventIdCard.Role.MENTOR if crew == "Mentor" else EventIdCard.Role.CREW
    try:
        from .speaker_identity_models import EventSpeaker
        if registration.member_id and EventSpeaker.objects.filter(event=event, user_id=registration.member_id).exists():
            return EventIdCard.Role.SPEAKER
    except Exception:
        pass
    return EventIdCard.Role.ATTENDEE


@transaction.atomic
def reconcile_event(event_id, actor=None):
    """Issue missing cards and revoke cards of registrations that ended. -> (issued, revoked)."""
    from apps.card_designs.lifecycle import on_issue, on_revoke
    from apps.card_designs.switches import event_cards_on
    event = Event.objects.select_related("makerspace").filter(pk=event_id).first()
    if event is None or not event_cards_on(event.makerspace) or not has_published_design(event):
        return 0, 0
    live = {card.registration_id: card for card in EventIdCard.objects.select_for_update().filter(
        event=event, status=EventIdCard.Status.ACTIVE)}
    confirmed = EventRegistration.objects.filter(event=event, status__in=CONFIRMED)
    issued = 0
    for registration in confirmed.exclude(pk__in=list(live)):
        card = EventIdCard.objects.create(event=event, makerspace_id=event.makerspace_id, registration=registration,
                                          person_id=registration.member_id, role=_role(event, registration),
                                          printed_name=registration.name or "", valid_until=valid_until(event))
        on_issue("event_card", card)
        audit.record(actor, "event_card.issued", makerspace=event.makerspace, target=card,
                     meta={"card_id": card.pk, "event_id": event.pk, "registration_id": registration.pk})
        from apps.card_designs.notifications import card_issued
        transaction.on_commit(lambda pk=card.pk: card_issued("event_card", pk), robust=True)
        issued += 1
    ended = [card for registration_id, card in live.items()
             if not confirmed.filter(pk=registration_id).exists()]
    for card in ended:
        _revoke_locked(actor, card, "Registration ended.")
        on_revoke("event_card", card)
    return issued, len(ended)


def _revoke_locked(actor, card, reason):
    card.status, card.revoked_at, card.revoked_by = EventIdCard.Status.REVOKED, timezone.now(), actor
    card.revoked_reason = reason[:300]
    card.save(update_fields=["status", "revoked_at", "revoked_by", "revoked_reason", "updated_at"])
    audit.record(actor, "event_card.revoked", makerspace=card.makerspace, target=card,
                 meta={"card_id": card.pk, "event_id": card.event_id})


@transaction.atomic
def revoke(actor, card, reason):
    from apps.card_designs.lifecycle import on_revoke
    if not (reason or "").strip():
        raise ValidationError({"reason": "Give a reason (it stays private to the organisers)."})
    card = EventIdCard.objects.select_for_update().get(pk=card.pk)
    if card.status != EventIdCard.Status.ACTIVE:
        return card
    _revoke_locked(actor, card, reason.strip())
    on_revoke("event_card", card)
    return card


@transaction.atomic
def set_role(actor, card, role):
    if role not in EventIdCard.Role.values:
        raise ValidationError({"role": "Choose attendee, speaker, mentor, judge, volunteer or crew."})
    if card.role != role:
        card.role = role
        card.save(update_fields=["role", "updated_at"])
        audit.record(actor, "event_card.role_changed", makerspace=card.makerspace, target=card,
                     meta={"card_id": card.pk, "event_id": card.event_id, "role": role})
    return card


def reconcile_due(limit=50):
    """Events with a published card design that are live or upcoming."""
    from apps.card_designs.models import CardDesign
    now = timezone.now()
    events = Event.objects.filter(ends_at__gte=now - VALID_AFTER_END, makerspace__enabled_modules__contains=["events"])
    spaces = CardDesign.objects.filter(domain="event_card", event__isnull=True, published_document__isnull=False) \
        .values_list("makerspace_id", flat=True)
    with_design = CardDesign.objects.filter(domain="event_card", published_document__isnull=False,
                                            event__isnull=False).values_list("event_id", flat=True)
    rows = events.filter(pk__in=with_design) | events.filter(makerspace_id__in=spaces)
    return list(rows.order_by("starts_at").values_list("pk", flat=True).distinct()[:limit])
