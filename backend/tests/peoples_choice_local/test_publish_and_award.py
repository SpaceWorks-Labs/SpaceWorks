"""People's choice count, publish once, the public block, badges and the prize payout (#181 S3)."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.judging import peoples_choice, peoples_choice_payouts, peoples_choice_results, payouts
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_payouts import HackathonPrizePayout
from apps.events.judging.models_peoples_choice import PeoplesChoiceResult, PeoplesChoiceStanding, PeoplesChoiceVote
from tests.events.pairwise_helpers import command
from tests.peoples_choice_local.helpers import close_voting, config_version, configure, enable, gallery_world, vote

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(settings, monkeypatch):
    world = gallery_world(settings, monkeypatch)
    configure(world)
    return world


def _votes(world, *entries):
    for voter, index in zip(world.voters, entries):
        vote(world, voter, world.entries[index])


def test_publish_waits_for_the_window_to_close(world):
    _votes(world, 0)
    with pytest.raises(ProgrammeError) as refused:
        peoples_choice_results.publish(world.event.pk, actor=world.manager, data=command(config_version(world)))
    assert refused.value.detail["code"] == "invalid_transition"
    assert not PeoplesChoiceResult.objects.exists()


def test_the_public_and_voters_see_no_count_before_publication(world):
    _votes(world, 0, 0, 1)
    public = peoples_choice_results.public_projection(world.event)
    assert public["state"] == "open" and public["award"] is None
    ballot = peoples_choice.read(world.event.pk, actor=world.manager)
    assert ballot["ballots"] == 3 and "standings" not in ballot
    assert peoples_choice_results.winning_snapshot_ids(world.event) == set()


def test_staff_count_ranks_and_skips_voided_and_hidden(world):
    _votes(world, 0, 0, 1, 2)
    # The void workflow is covered in test_voting; here only the count matters.
    from apps.events.judging.models_scoring import JudgingReason
    reason = JudgingReason.objects.create(event=world.event, makerspace_id=world.space.pk, body="Test")
    PeoplesChoiceVote.objects.filter(event=world.event, voter=world.voters[3]).update(
        voided_at=timezone.now(), void_reason=reason)
    rows = peoples_choice_results.standings(world.event.pk, actor=world.manager)["standings"]
    assert [(row["snapshot_id"], row["votes"], row["rank"], row["winner"]) for row in rows] == [
        (world.snapshots[0], 2, 1, True), (world.snapshots[1], 1, 2, False)]
    type(world.entries[0]).objects.filter(pk=world.entries[0].pk).update(hidden_at=timezone.now())
    rows = peoples_choice_results.standings(world.event.pk, actor=world.manager)["standings"]
    assert [row["snapshot_id"] for row in rows] == [world.snapshots[1]]


def test_publish_once_freezes_joint_winners_and_ends_voting(world):
    _votes(world, 0, 1, 0, 1)
    close_voting(world)
    published = peoples_choice_results.publish(world.event.pk, actor=world.manager, data=command(config_version(world)))
    assert published["published"] is True and published["total_votes"] == 4
    winners = PeoplesChoiceStanding.objects.filter(result__event=world.event, winner=True)
    assert set(winners.values_list("submission_snapshot_id", flat=True)) == set(world.snapshots[:2])
    assert set(winners.values_list("rank", flat=True)) == {1}
    assert AuditLog.objects.filter(action="event.peoples_choice.published").exists()
    with pytest.raises(ProgrammeError) as twice:
        peoples_choice_results.publish(world.event.pk, actor=world.manager, data=command(config_version(world)))
    assert twice.value.detail["code"] == "already_published"
    with pytest.raises(ProgrammeError) as final:
        peoples_choice.update(world.event.pk, actor=world.manager, data=command(config_version(world), enabled=False))
    assert final.value.detail["code"] == "already_published"
    with pytest.raises(ProgrammeError) as ended:
        vote(world, world.voters[0], world.entries[2], version=1)
    assert ended.value.detail["code"] == "published"


def test_published_rows_are_append_only(world):
    _votes(world, 0)
    close_voting(world)
    peoples_choice_results.publish(world.event.pk, actor=world.manager, data=command(config_version(world)))
    result = PeoplesChoiceResult.objects.get(event=world.event)
    with pytest.raises(RuntimeError):
        result.save()
    with pytest.raises(RuntimeError):
        PeoplesChoiceStanding.objects.filter(result=result).update(votes=99)


def test_public_award_names_winners_and_badges_follow_publication(world):
    _votes(world, 2, 2, 0)
    close_voting(world)
    peoples_choice_results.publish(world.event.pk, actor=world.manager, data=command(config_version(world)))
    public = peoples_choice_results.public_projection(world.event)
    assert public["state"] == "published"
    assert public["award"]["prize_name"] == "People's choice" and public["award"]["total_votes"] == 3
    assert [(w["title"], w["votes"], w["entry_public_id"]) for w in public["award"]["winners"]] == [
        (world.ports.snaps[world.snapshots[2]].title, 2, world.entries[2].public_id)]
    assert peoples_choice_results.winning_snapshot_ids(world.event) == {world.snapshots[2]}


def test_no_votes_means_no_winner(world):
    close_voting(world)
    published = peoples_choice_results.publish(world.event.pk, actor=world.manager, data=command(config_version(world)))
    assert published["standings"] == [] and published["total_votes"] == 0
    assert peoples_choice_results.public_projection(world.event)["award"]["winners"] == []


def test_judging_is_untouched(world):
    from apps.events.judging.models_results import EventAward, EventResultRevision
    _votes(world, 0)
    close_voting(world)
    peoples_choice_results.publish(world.event.pk, actor=world.manager, data=command(config_version(world)))
    assert not EventResultRevision.objects.filter(event=world.event).exists()
    assert not EventAward.objects.exists()


def _prize(world, amount="150.00"):
    from apps.events.judging.definitions_workflow import save_definition
    return save_definition(world.event.pk, actor=world.manager, kind="prizes",
                           data=command(name="Crowd favourite", amount_per_winner=amount))["id"]


def test_a_prize_winner_is_paid_once_through_the_ledger_and_can_be_reversed(world):
    from apps.payments.models_ledger_entries import LedgerEntry
    enable(world, "charges.enabled", "charges.events", "events.prize_payouts")
    configure(world, prize_id=_prize(world))
    _votes(world, 1)
    close_voting(world)
    peoples_choice_results.publish(world.event.pk, actor=world.manager, data=command(config_version(world)))
    winners = peoples_choice_payouts.payable(world.event.pk, actor=world.manager)
    assert [(row["prize_name"], row["paid"]) for row in winners] == [("Crowd favourite", False)]
    row = peoples_choice_payouts.record_payout(world.event.pk, actor=world.manager, data=command(
        0, standing_id=winners[0]["id"], method="upi", reference="UPI-1", paid_on="2026-11-05"))
    assert row["award_id"] is None and row["peoples_choice_standing_id"] == winners[0]["id"]
    entry = LedgerEntry.objects.get(pk=row["ledger_entry_id"])
    assert (entry.kind, entry.category, entry.amount) == ("expense", "prize", Decimal("150.00"))
    with pytest.raises(ProgrammeError) as twice:
        peoples_choice_payouts.record_payout(world.event.pk, actor=world.manager, data=command(
            0, standing_id=winners[0]["id"], method="cash", reference="REF-1", paid_on="2026-11-05"))
    assert twice.value.detail["code"] == "payout_exists"
    reversal = payouts.reverse_payout(world.event.pk, row["id"], actor=world.manager, data=command(0, reason="Wrong payee"))
    assert reversal["kind"] == "reversal" and reversal["peoples_choice_standing_id"] == winners[0]["id"]
    assert HackathonPrizePayout.objects.filter(peoples_choice_standing_id=winners[0]["id"]).count() == 2


def test_an_award_without_a_prize_has_nothing_to_pay(world):
    enable(world, "charges.enabled", "charges.events", "events.prize_payouts")
    _votes(world, 0)
    close_voting(world)
    peoples_choice_results.publish(world.event.pk, actor=world.manager, data=command(config_version(world)))
    assert peoples_choice_payouts.payable(world.event.pk, actor=world.manager) == []
