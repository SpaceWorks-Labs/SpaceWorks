"""Which badge role a registration prints as (parity E-B2, I24) and how a hand-set role sticks.

Precedence, first match wins: an organiser (approved co-organiser, or crew of kind organiser); a contributor
judge, mentor or volunteer; crew (a crew kind of volunteer, mentor or judge keeps that role, any other crew is
`crew`); a speaker; otherwise an attendee. While `events.role_badges` is off only the original three
distinctions are made (crew, mentor, speaker), so switching the feature on or off never changes a card that
nobody asked to change. A role chosen by hand sets `role_locked`; detection never overwrites a locked card.
"""
from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .models import EventIdCard

Role = EventIdCard.Role
CONTRIBUTOR_ROLES = {"judge": Role.JUDGE, "mentor": Role.MENTOR, "volunteer": Role.VOLUNTEER}
KIND_ROLES = {"organiser": Role.ORGANISER, "volunteer": Role.VOLUNTEER, "mentor": Role.MENTOR, "judge": Role.JUDGE}


def role_badges_enabled(event):
    from apps.card_designs.switches import role_badges_on
    return role_badges_on(event.makerspace)


def _assignment_roles(event, member_id):
    if not member_id:
        return set()
    from .contributions.models_roles import EventRoleAssignment
    return set(EventRoleAssignment.objects.filter(event=event, member_id=member_id, state="approved").values_list(
        "role", flat=True))


def _speaker(event, member_id):
    try:
        from .speaker_identity_models import EventSpeaker
        return bool(member_id) and EventSpeaker.objects.filter(event=event, user_id=member_id).exists()
    except Exception:
        return False


def detect_role(event, registration):
    """-> an `EventIdCard.Role` value for this registration."""
    from .contributions.crew_reads import crew_kind_for, crew_labels
    crew = crew_labels(event, [registration.pk]).get(registration.pk)
    if not role_badges_enabled(event):
        if crew is not None:
            return Role.MENTOR if crew == "Mentor" else Role.CREW
        return Role.SPEAKER if _speaker(event, registration.member_id) else Role.ATTENDEE
    assigned = _assignment_roles(event, registration.member_id)
    kind = crew_kind_for(event, registration.pk) if crew is not None else ""
    if "co_organizer" in assigned or kind == "organiser":
        return Role.ORGANISER
    for contributor, role in CONTRIBUTOR_ROLES.items():
        if contributor in assigned:
            return role
    if crew is not None:
        return KIND_ROLES.get(kind) or (Role.MENTOR if crew == "Mentor" else Role.CREW)
    return Role.SPEAKER if _speaker(event, registration.member_id) else Role.ATTENDEE


def redetect(event, actor=None):
    """Re-run role detection for this event's live cards that were not set by hand. -> number changed."""
    if not role_badges_enabled(event):
        return 0
    changed = 0
    for card in EventIdCard.objects.select_for_update().select_related("registration").filter(
            event=event, status=EventIdCard.Status.ACTIVE, role_locked=False):
        role = detect_role(event, card.registration)
        if role != card.role:
            _change(actor, card, role)
            changed += 1
    return changed


def _change(actor, card, role):
    card.role = role
    card.save(update_fields=["role", "updated_at"])
    audit.record(actor, "event_card.role_changed", makerspace=card.makerspace, target=card,
                 meta={"card_id": card.pk, "event_id": card.event_id, "role": role})


@transaction.atomic
def set_role(actor, card, role=None, locked=None):
    """Staff set a card's role by hand (locking it) or release the lock (`locked=False`) to re-detect it."""
    card = EventIdCard.objects.select_for_update().select_related("registration", "event__makerspace").get(pk=card.pk)
    if role is not None and role not in Role.values:
        raise ValidationError({"role": gettext(
            "Choose attendee, speaker, mentor, judge, volunteer, crew or organiser.")})
    if role is None and locked is None:
        raise ValidationError({"role": gettext("Choose a role, or release the lock.")})
    if locked is False and role is None:
        role = detect_role(card.event, card.registration)
    if role is not None and card.role != role:
        _change(actor, card, role)
    want_lock = (role is not None) if locked is None else bool(locked)
    if card.role_locked != want_lock:
        card.role_locked = want_lock
        card.save(update_fields=["role_locked", "updated_at"])
        audit.record(actor, "event_card.role_locked", makerspace=card.makerspace, target=card,
                     meta={"card_id": card.pk, "event_id": card.event_id, "role": card.role, "locked": want_lock})
    return card
