"""GAP crew: the crew chip (cards, tickets, badges), the crew Pages section, funnel stages, series ids."""
from types import SimpleNamespace

import pytest

from apps.events import id_cards
from apps.events.badge_templates import DEFAULT_BADGE_TEMPLATE, SAFE_FIELDS
from apps.events.certificates.layout import TAGS
from apps.events.contributions import crew_reads, crew_workflow
from apps.events.models import EventCrewMember, EventIdCard, EventParticipationSettings
from apps.events.services_badges import prepare_badges
from apps.makerspaces.public_page_contract import SECTION_TYPES
from apps.makerspaces.public_page_crew import crew_section
from tests.events.collab_helpers import make_event, make_member, make_space, make_staff
from tests.events.test_registration_cancel_api import register

pytestmark = pytest.mark.django_db


def world(slug, *features):
    space = make_space(slug)
    space.enabled_features = ["charges.enabled", *features]
    space.save(update_fields=["enabled_features"])
    event = make_event(space, is_public=True)
    return space, event, make_staff(space)


def crew_member(event, staff, space, username, role):
    member = make_member(space, username)
    crew = crew_workflow.add(event, actor=staff, member=member, crew_role=role)
    return member, EventCrewMember.objects.get(pk=crew.pk)


def test_crew_labels_follow_the_switch_and_name_mentors():
    space, event, staff = world("chip-a", "events.crew")
    _, mentor = crew_member(event, staff, space, "chip-mentor", "mentor")
    _, door = crew_member(event, staff, space, "chip-door", "Door")
    _, plain = crew_member(event, staff, space, "chip-plain", "")
    participant = register(event, make_member(space, "chip-p"))
    ids = [mentor.registration_id, door.registration_id, plain.registration_id, participant.pk]
    assert crew_reads.crew_labels(event, ids) == {mentor.registration_id: "Mentor", door.registration_id: "Door",
                                                  plain.registration_id: "Crew"}
    space.enabled_features = ["charges.enabled"]
    space.save(update_fields=["enabled_features"])
    assert crew_reads.crew_labels(event, ids) == {}  # data kept, chip hidden while the switch is off


def test_event_card_role_comes_from_the_crew_place():
    space, event, staff = world("chip-b", "events.crew")
    _, mentor = crew_member(event, staff, space, "chip-b-mentor", "Mentor")
    _, door = crew_member(event, staff, space, "chip-b-door", "Door")
    participant = register(event, make_member(space, "chip-b-p"))
    assert id_cards._role(event, mentor.registration) == EventIdCard.Role.MENTOR
    assert id_cards._role(event, door.registration) == EventIdCard.Role.CREW
    assert id_cards._role(event, participant) == EventIdCard.Role.ATTENDEE


def test_badges_print_the_crew_role_and_blank_for_participants():
    assert "crew_role" in SAFE_FIELDS and "crewRole" in TAGS
    space, event, staff = world("chip-c", "events.crew")
    _, door = crew_member(event, staff, space, "chip-c-door", "Door")
    participant = register(event, make_member(space, "chip-c-p"))
    template = {**DEFAULT_BADGE_TEMPLATE, "fields": ["name", "crew_role"], "elements": []}
    _, snapshots = prepare_badges(event, [door.registration_id, participant.pk], actor=staff,
                                  template_override=template)
    by_id = {row.registration_id: dict(row.fields) for row in snapshots}
    assert by_id[door.registration_id]["Crew"] == "Door"
    assert by_id[participant.pk]["Crew"] == ""


def test_credential_badge_snapshot_carries_crew_role(monkeypatch):
    from apps.events.certificates import print_workflow
    space, event, staff = world("chip-d", "events.crew")
    _, door = crew_member(event, staff, space, "chip-d-door", "AV")
    qr = SimpleNamespace(registration=door.registration, registration_id=door.registration_id, pk=1,
                         credential_generation=1)

    class Resources:
        def filter(self, **kwargs):
            if kwargs.get("kind") == "qr":
                return SimpleNamespace(select_related=lambda *a: [qr])
            return SimpleNamespace(first=lambda: None)

    from django.utils import timezone
    job = SimpleNamespace(resources=Resources(), event=event, event_id=event.pk, template_revision_id=1,
                          stock="a6", created_at=timezone.now(), expires_at=timezone.now())
    (snapshot,) = print_workflow.snapshots(job)
    assert dict(snapshot.authorized_fields)["crewRole"] == "AV"


def test_crew_pages_section_is_event_only_opt_in_and_public_fields_only():
    assert "crew" in SECTION_TYPES["event"]
    assert "crew" not in SECTION_TYPES["makerspace"] and "crew" not in SECTION_TYPES["organization"]
    space, event, staff = world("pages-crew", "events.crew")
    member, crew = crew_member(event, staff, space, "pages-crew-m", "Host")
    EventCrewMember.objects.filter(pk=crew.pk).update(show_publicly=True)
    # No public profile: never shown, so the section renders nothing at all.
    assert crew_section("event", event, "Crew") is None
    assert crew_section("makerspace", space, "Crew") is None
    EventParticipationSettings.objects.create(makerspace=space, event=event, crew_public_section=False)
    from unittest import mock
    card = {"handle": "host", "display_name": "Host Person", "crew_role": "Host"}
    with mock.patch("apps.events.contributions.crew_reads.public_crew", return_value=[card]) as reader:
        assert crew_section("event", event, "Our crew") == {"title": "Our crew", "results": [card]}
        reader.assert_called_once_with(event, require_switch=False)
    space.enabled_features = ["charges.enabled"]
    space.save(update_fields=["enabled_features"])
    assert crew_section("event", event, "Crew") is None


def test_public_crew_per_event_block_still_needs_its_switch():
    space, event, staff = world("pages-crew-b", "events.crew")
    _, crew = crew_member(event, staff, space, "pages-crew-b-m", "Host")
    EventCrewMember.objects.filter(pk=crew.pk).update(show_publicly=True)
    assert crew_reads.public_crew(event) == []


def test_public_series_carries_id_and_passes_switch():
    from apps.events.serializers_public import PublicEventSerializer
    space, _, _ = world("series-id", "events.ticket_types", "events.orders", "events.series_passes")  # series passes require orders, which require ticket types
    event = SimpleNamespace(series_id=5, series=SimpleNamespace(public_token="token", title="Build nights"), makerspace=space)
    data = PublicEventSerializer().get_series(event)
    assert data == {"public_token": "token", "title": "Build nights", "id": 5, "passes_enabled": True}
    space.enabled_features = ["charges.enabled"]
    space.save(update_fields=["enabled_features"])
    assert PublicEventSerializer().get_series(event)["passes_enabled"] is False
    assert PublicEventSerializer().get_series(SimpleNamespace(series_id=None)) is None
