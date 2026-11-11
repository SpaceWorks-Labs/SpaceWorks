"""People's choice stands on final-stage work only (re-trace gap 18; #181 S3 x #178/#180 S18).

An earlier stage made public early (`public_after_publish`) shows its entries in the gallery, but
`stage_gallery.final_stage_entries` keeps them out of the ballot, the member's own-entry read and the
count.
"""

from datetime import timedelta

import pytest
from django.http import Http404
from django.utils import timezone

from apps.events.judging import peoples_choice_votes
from apps.events.judging.peoples_choice_results import tally
from apps.events.submissions.models_stages import SnapshotStage, SubmissionStage
from tests.peoples_choice_local.helpers import configure, gallery_world, vote

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(settings, monkeypatch):
    return gallery_world(settings, monkeypatch, projects=3)


def _two_stages_with_first_entry_early(world):
    now = timezone.now()
    first = SubmissionStage.objects.create(event=world.event, position=1, name="Idea",
                                           deadline=now + timedelta(days=1), public_after_publish=True)
    final = SubmissionStage.objects.create(event=world.event, position=2, name="Final",
                                           deadline=now + timedelta(days=2))
    early, *rest = world.entries
    SnapshotStage.objects.create(snapshot_id=early.snapshot_id, stage=first)
    for entry in rest:
        SnapshotStage.objects.create(snapshot_id=entry.snapshot_id, stage=final)
    return early, rest


def test_an_early_stage_entry_cannot_be_chosen(world):
    configure(world)
    early, rest = _two_stages_with_first_entry_early(world)
    with pytest.raises(Http404):
        vote(world, world.voters[0], early)
    vote(world, world.voters[1], rest[0])  # Final-stage work still takes a vote.


def test_the_count_leaves_early_stage_entries_out(world):
    configure(world)
    vote(world, world.voters[0], world.entries[0])  # Cast while the event had no stages.
    vote(world, world.voters[1], world.entries[1])
    early, _rest = _two_stages_with_first_entry_early(world)
    counted = {row["snapshot_id"] for row in tally(world.event)}
    assert early.snapshot_id not in counted
    assert world.entries[1].snapshot_id in counted


def test_a_stage_less_event_keeps_every_live_entry(world):
    configure(world)
    for voter, entry in zip(world.voters, world.entries):
        vote(world, voter, entry)
    assert {row["snapshot_id"] for row in tally(world.event)} == {entry.snapshot_id for entry in world.entries}


def test_the_ballot_never_offers_an_early_entry_as_the_voters_own(world):
    configure(world)
    early, _rest = _two_stages_with_first_entry_early(world)
    team_id = early.snapshot.submission.team_id
    assert peoples_choice_votes._entry_for_team(world.event, team_id) is None
