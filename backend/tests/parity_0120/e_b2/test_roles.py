"""I24: role detection (organiser, judge/mentor/volunteer, crew kinds, speaker), the lock, the switch."""
import pytest

from apps.audit.models import AuditLog
from apps.events import id_cards
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.id_cards_roles import detect_role, redetect, set_role
from apps.events.models import EventIdCard
from tests.l3_local.helpers import client
from tests.parity_0120.e_b2.helpers import FEATURES, issue_cards, live_event, publish_badge, register

pytestmark = pytest.mark.django_db


def _assign(event, user, role):
    return EventRoleAssignment.objects.create(event=event, makerspace=event.makerspace, member=user, role=role,
                                              state="approved")


def test_precedence_organiser_then_contributor_then_attendee():
    space, event, _sm = live_event("e2-roles")
    user, registration = register(space, event, "judge")
    assert detect_role(event, registration) == EventIdCard.Role.ATTENDEE
    _assign(event, user, "judge")
    assert detect_role(event, registration) == EventIdCard.Role.JUDGE
    _assign(event, user, "co_organizer")
    assert detect_role(event, registration) == EventIdCard.Role.ORGANISER


def test_role_switch_off_keeps_the_original_three_roles_only():
    space, event, _sm = live_event("e2-roles-off", features=tuple(f for f in FEATURES if f != "events.role_badges"))
    user, registration = register(space, event, "judge")
    _assign(event, user, "judge")
    assert detect_role(event, registration) == EventIdCard.Role.ATTENDEE


def test_reconcile_redetects_but_a_hand_set_role_sticks_and_is_audited():
    space, event, sm = live_event("e2-lock")
    publish_badge(space, event, sm)
    user, registration = register(space, event, "vol")
    other, other_registration = register(space, event, "other")
    cards = issue_cards(event)
    assert cards[registration.pk].role == "attendee"
    _assign(event, user, "volunteer")
    _assign(event, other, "volunteer")
    set_role(sm, cards[other_registration.pk], "speaker")  # by hand: locks
    id_cards.reconcile_event(event.pk)
    cards = {card.registration_id: card for card in EventIdCard.objects.filter(event=event)}
    assert cards[registration.pk].role == "volunteer" and not cards[registration.pk].role_locked
    assert cards[other_registration.pk].role == "speaker" and cards[other_registration.pk].role_locked
    assert AuditLog.objects.filter(action="event_card.role_locked").exists()
    assert AuditLog.objects.filter(action="event_card.role_changed").count() >= 2
    set_role(sm, cards[other_registration.pk], locked=False)  # releasing re-detects
    cards[other_registration.pk].refresh_from_db()
    assert cards[other_registration.pk].role == "volunteer" and not cards[other_registration.pk].role_locked


def test_patch_sets_the_role_and_needs_edit_authority():
    space, event, sm = live_event("e2-patch")
    publish_badge(space, event, sm)
    _user, registration = register(space, event, "p")
    card = issue_cards(event)[registration.pk]
    response = client(sm).patch(f"/api/v1/admin/event-id-cards/{card.pk}", {"role": "organiser"}, format="json")
    assert response.status_code == 200 and response.json()["role"] == "organiser" and response.json()["role_locked"]
    assert client(sm).patch(f"/api/v1/admin/event-id-cards/{card.pk}", {"role": "nope"}, format="json").status_code == 400


def test_a_role_variant_alone_does_not_make_the_event_ready():
    space, event, sm = live_event("e2-ready")
    assert not id_cards.has_published_design(event)
    publish_badge(space, event, sm, role="crew")
    assert not id_cards.has_published_design(event)
    publish_badge(space, event, sm)
    assert id_cards.has_published_design(event)
