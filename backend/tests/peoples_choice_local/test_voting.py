"""People's choice settings and voting (#181 S3): one ballot per person, never your own team, the audience."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.events.judging import peoples_choice, peoples_choice_ballots, peoples_choice_votes
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_peoples_choice import PeoplesChoiceConfig, PeoplesChoiceVote
from apps.events.models import EventRegistration
from tests.events.pairwise_helpers import command
from tests.events.ticketing_helpers import account
from tests.peoples_choice_local.helpers import configure, disable, gallery_world, vote

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(settings, monkeypatch):
    return gallery_world(settings, monkeypatch)


def test_capability_is_under_events_off_by_default_and_needs_the_gallery():
    from apps.makerspaces.capability_definitions import FEATURES
    definition = FEATURES["events.peoples_choice"]
    assert definition.parent_module == "events" and definition.default_enabled is False
    assert definition.requires_features == ("events.project_gallery",)


def test_switched_off_everything_is_not_found_and_data_is_kept(world):
    configure(world)
    vote(world, world.voters[0], world.entries[0])
    disable(world, "events.peoples_choice")
    with pytest.raises(Http404):
        peoples_choice.read(world.event.pk, actor=world.manager)
    with pytest.raises(Http404):
        peoples_choice_votes.ballot(world.event, actor=world.voters[0])
    with pytest.raises(Http404):
        vote(world, world.voters[1], world.entries[0])
    assert PeoplesChoiceVote.objects.filter(event=world.event).count() == 1


def test_new_events_start_off_and_settings_are_versioned_and_audited(world):
    state = peoples_choice.read(world.event.pk, actor=world.manager)
    assert (state["enabled"], state["state"], state["version"], state["audience"]) == (False, "off", 0, "members")
    saved = configure(world, audience="attendees")
    assert (saved["enabled"], saved["state"], saved["audience"], saved["version"]) == (True, "open", "attendees", 1)
    entry = AuditLog.objects.filter(action="event.peoples_choice.updated").latest("pk")
    assert entry.meta["fields"] == ["audience", "enabled"]
    with pytest.raises(ProgrammeError) as stale:
        peoples_choice.update(world.event.pk, actor=world.manager, data=command(0, enabled=False))
    assert stale.value.detail["code"] == "stale_version"


def test_window_order_and_foreign_prizes_are_refused(world):
    now = timezone.now()
    with pytest.raises(ValidationError):
        configure(world, opens_at=now.isoformat(), closes_at=(now - timedelta(hours=1)).isoformat())
    with pytest.raises(ValidationError):
        configure(world, prize_id=987654)


def test_a_member_votes_once_and_may_change_it(world):
    configure(world)
    voter = world.voters[0]
    first = vote(world, voter, world.entries[0])
    assert first["entry_public_id"] == str(world.entries[0].public_id) and first["version"] == 1
    same = vote(world, voter, world.entries[0], version=1)
    assert same["version"] == 1  # The same choice changes nothing.
    moved = vote(world, voter, world.entries[1], version=1)
    assert moved["version"] == 2 and moved["entry_public_id"] == str(world.entries[1].public_id)
    assert PeoplesChoiceVote.objects.filter(event=world.event, voter=voter).count() == 1
    with pytest.raises(ProgrammeError) as stale:
        vote(world, voter, world.entries[2], version=1)
    assert stale.value.detail["code"] == "stale_version"


def test_the_database_holds_one_ballot_per_person(world):
    team = world.entries[0].snapshot.submission.team_id
    PeoplesChoiceVote.objects.create(event=world.event, voter=world.voters[0], team_id=team)
    with pytest.raises(IntegrityError), transaction.atomic():
        PeoplesChoiceVote.objects.create(event=world.event, voter=world.voters[0], team_id=team)


def test_the_audit_row_never_names_the_project(world):
    configure(world)
    vote(world, world.voters[0], world.entries[0])
    entry = AuditLog.objects.filter(action="event.peoples_choice.ballot_cast").latest("pk")
    assert set(entry.meta) == {"event_id", "changed"}
    assert entry.target_id == str(world.event.pk)  # The event, never the ballot or the team.


def test_nobody_votes_for_their_own_team(world):
    configure(world)
    leader = world.ports.snaps[world.snapshots[0]].member_ids[0]
    from apps.accounts.models import User
    with pytest.raises(ProgrammeError) as own:
        vote(world, User.objects.get(pk=leader), world.entries[0])
    assert own.value.detail["code"] == "own_project"
    ballot = peoples_choice_votes.ballot(world.event, actor=User.objects.get(pk=leader))
    assert ballot["own_entry_public_ids"] == [world.entries[0].public_id]


def test_attendees_only_needs_a_check_in(world):
    configure(world, audience="attendees")
    voter = world.voters[0]
    with pytest.raises(ProgrammeError) as refused:
        vote(world, voter, world.entries[0])
    assert refused.value.detail["code"] == "attendees_only"
    EventRegistration.objects.create(event=world.event, member=voter, name="V", email="v@example.test", phone="1",
                                     status=EventRegistration.Status.ATTENDED)
    assert vote(world, voter, world.entries[0])["version"] == 1


@pytest.mark.parametrize("window, code", [
    ({"opens_at": timedelta(hours=1)}, "not_open"),
    ({"opens_at": -timedelta(hours=2), "closes_at": -timedelta(minutes=1)}, "closed"),
])
def test_votes_only_inside_the_window(world, window, code):
    now = timezone.now()
    configure(world, **{key: (now + delta).isoformat() for key, delta in window.items()})
    with pytest.raises(ProgrammeError) as refused:
        vote(world, world.voters[0], world.entries[0])
    assert refused.value.detail["code"] == code


def test_only_a_live_public_project_can_be_chosen(world):
    configure(world)
    hidden = world.entries[2]
    type(hidden).objects.filter(pk=hidden.pk).update(hidden_at=timezone.now())
    with pytest.raises(Http404):
        vote(world, world.voters[0], hidden)


def test_a_voided_ballot_stops_counting_and_cannot_be_recast(world):
    configure(world)
    voter = world.voters[0]
    vote(world, voter, world.entries[0])
    row = PeoplesChoiceVote.objects.get(event=world.event, voter=voter)
    voided = peoples_choice_ballots.void(world.event.pk, row.handle, actor=world.manager,
                                         data=command(row.version, reason="Duplicate account"))
    assert voided["voided"] is True and voided["void_reason"] == "Duplicate account"
    with pytest.raises(ProgrammeError) as again:
        vote(world, voter, world.entries[1], version=row.version + 1)
    assert again.value.detail["code"] == "voided"
    assert PeoplesChoiceVote.objects.filter(event=world.event, voter=voter).count() == 1
    assert AuditLog.objects.filter(action="event.peoples_choice.vote_voided").exists()


def test_staff_ballot_list_shows_who_voted_never_the_project(world):
    configure(world)
    vote(world, world.voters[0], world.entries[0])
    _event, rows = peoples_choice_ballots.listing(world.event.pk, actor=world.manager)
    assert len(rows) == 1
    assert set(rows[0]) == {"handle", "voter_name", "attended", "changed", "voided", "void_reason", "version",
                            "allowed_actions"}


def test_a_staff_only_account_cannot_vote(world):
    # U-A1: one account per person, the role decides -- so a Space Manager is a person and may vote (for
    # another team's project). What cannot vote is an account that is not a person (platform / inert shell).
    from apps.accounts.models import User
    configure(world)
    shell = account(f"shell-{uuid4().hex[:8]}", account_kind=User.AccountKind.PLATFORM)  # kind is immutable: create it so
    with pytest.raises(Exception):
        vote(world, shell, world.entries[0])
    assert not PeoplesChoiceVote.objects.filter(voter=shell).exists()


def test_the_vote_route_has_its_own_throttle():
    from django.conf import settings
    from apps.events.judging.views_peoples_choice import MemberPeoplesChoiceVote
    assert MemberPeoplesChoiceVote.throttle_scope == "peoples_choice_vote"
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["peoples_choice_vote"] == "20/hour"


def test_config_row_is_one_per_event(world):
    configure(world)
    with pytest.raises(IntegrityError), transaction.atomic():
        PeoplesChoiceConfig.objects.create(event=world.event)
