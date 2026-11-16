"""People's choice prizes follow the judged-prize money rules (#181 S3 x hack-money G6/G7/G16)."""

from decimal import Decimal

import pytest

from apps.events.judging import peoples_choice_money, peoples_choice_payouts, peoples_choice_results, prize_outcomes
from apps.events.judging.models_prize_money import HackathonPrizeOutcome
from apps.events.judging.prize_reads import prize_pool
from apps.events.submissions.models_projects import SubmissionSnapshot
from tests.events.pairwise_helpers import command
from tests.hackmoney_local.prize_helpers import tax_on
from tests.peoples_choice_local.helpers import close_voting, config_version, configure, enable, gallery_world, vote

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(settings, monkeypatch):
    world = gallery_world(settings, monkeypatch)
    enable(world, "charges.enabled", "charges.events", "events.prize_payouts")
    from apps.events.judging.definitions_workflow import save_definition
    prize_id = save_definition(world.event.pk, actor=world.manager, kind="prizes",
                               data=command(name="Crowd favourite", amount_per_winner="20000.00"))["id"]
    configure(world, prize_id=prize_id)
    vote(world, world.voters[0], world.entries[1])
    close_voting(world)
    peoples_choice_results.publish(world.event.pk, actor=world.manager, data=command(config_version(world)))
    return world


def _pay(world, **fields):
    winner = peoples_choice_payouts.payable(world.event.pk, actor=world.manager)[0]
    return winner, peoples_choice_payouts.record_payout(world.event.pk, actor=world.manager, data=command(
        0, standing_id=winner["id"], method="upi", reference="UPI-1", paid_on="2026-11-05", **fields))


def test_the_space_tax_proposal_applies_to_a_peoples_choice_payout(world):
    tax_on(world)
    winner, row = _pay(world)
    assert winner["tax_proposal"]["enabled"] is True
    assert (Decimal(row["amount"]), Decimal(row["tds_amount"]), Decimal(row["net_amount"])) == (
        Decimal("20000.00"), Decimal("6000.00"), Decimal("14000.00"))


def test_an_explicit_zero_records_no_tax(world):
    tax_on(world)
    _winner, row = _pay(world, tds_amount="0")
    assert Decimal(row["tds_amount"]) == Decimal("0") and Decimal(row["net_amount"]) == Decimal("20000.00")


def test_unpaid_winners_are_owed_until_paid(world):
    assert peoples_choice_money.owed(world.event) == Decimal("20000.00")
    assert prize_pool(world.event)["owed"] >= Decimal("20000.00")
    rows = peoples_choice_money.report_rows(world.event, "inr", lambda: None)
    assert [(row["prize"], row["status"], row["amount_outstanding"]) for row in rows] == [
        ("Crowd favourite", "owed", Decimal("20000.00"))]
    _pay(world)
    assert peoples_choice_money.owed(world.event) == Decimal("0")
    assert peoples_choice_money.report_rows(world.event, "inr", lambda: None) == []


def test_disqualifying_a_paid_winner_opens_a_recovery_on_its_payout(world):
    _winner, row = _pay(world)
    project = SubmissionSnapshot.objects.get(pk=world.entries[1].snapshot_id).submission
    opened = prize_outcomes.open_recoveries_locked(event=world.event, project=project, actor=world.manager)
    assert len(opened) == 1 and opened[0].award_id is None and opened[0].payout_id == row["id"]
    assert HackathonPrizeOutcome.objects.filter(kind="recovery_opened", payout_id=row["id"]).count() == 1
    report = peoples_choice_money.report_rows(world.event, "inr", lambda: None)
    assert [(item["status"], item["open_recoveries"]) for item in report] == [("paid", 1)]
