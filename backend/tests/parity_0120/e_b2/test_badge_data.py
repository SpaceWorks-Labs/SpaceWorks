"""The badge projection: email and answers only when printed, sensitive answers withheld, the check-in code
never rotated, the role variant design, sponsor logos and the face's check-in QR."""
import pytest

from apps.card_designs import cards, tokens
from apps.card_designs.holders import spec_for
from apps.events import badge_snapshot
from apps.events.badge_credentials import current_checkin_payload
from apps.events.models import EventIdCard
from tests.parity_0120.e_b2.helpers import issue_cards, live_event, publish_badge, register

pytestmark = pytest.mark.django_db


def _card(slug, **settings):
    space, event, sm = live_event(slug)
    publish_badge(space, event, sm, **settings)
    _user, registration = register(space, event, "ada")
    registration.custom_answers = {"company": "Acme", "diet": "vegan"}
    registration.save()
    return space, event, sm, registration, issue_cards(event)[registration.pk]


def test_email_and_answers_appear_only_when_the_design_prints_them():
    _s, _e, _sm, _registration, card = _card("e2-print", showEmail=False, printFieldKeys=["registration:company"],
                                             printFieldLabels={"registration:company": "Company"})
    values = spec_for("event_card").snapshot(card)
    assert values["field:company"] == "Acme"
    assert "field:diet" not in values and "email" not in values
    _s, _e, _sm, _r, with_email = _card("e2-email", showEmail=True)
    assert spec_for("event_card").snapshot(with_email)["email"] == with_email.registration.email


def test_a_sensitive_question_is_withheld(monkeypatch):
    _s, _event, _sm, _registration, card = _card("e2-sens", printFieldKeys=["registration:company"],
                                                 printFieldLabels={"registration:company": "Company"})
    monkeypatch.setattr(badge_snapshot, "allowed_keys", lambda _event: ({"other"}, True))
    assert "field:company" not in spec_for("event_card").snapshot(card)


def test_the_checkin_payload_is_the_legacy_token_and_a_v2_without_a_live_credential_never_rotates():
    _s, _e, _sm, registration, card = _card("e2-payload")
    assert spec_for("event_card").checkin_payload(card) == str(registration.checkin_token)
    registration.credential_mode = "v2"
    registration.save(update_fields=["credential_mode"])
    from apps.events.credentials.models import EventRegistrationCredential
    assert current_checkin_payload(registration) is None
    assert not EventRegistrationCredential.objects.filter(registration=registration).exists()


def test_the_role_variant_design_is_used_for_that_role():
    space, event, sm, _registration, card = _card("e2-variant")
    crew_design = publish_badge(space, event, sm, role="crew", badgeLabel="CREW")
    EventIdCard.objects.filter(pk=card.pk).update(role="crew")
    card = EventIdCard.objects.get(pk=card.pk)
    assert spec_for("event_card").design(card)[1].pk == crew_design.pk
    attendee_card = EventIdCard.objects.get(pk=card.pk)
    attendee_card.role = "attendee"
    assert spec_for("event_card").design(attendee_card)[1].pk != crew_design.pk


def test_the_rendered_card_context_carries_the_checkin_code():
    _s, _e, _sm, registration, card = _card("e2-context")
    document = cards.document_for("event_card", card)
    context = cards.context_for("event_card", card, document)
    assert context.checkin_qr == str(registration.checkin_token)
    assert tokens.live("event_card", card) is not None
