"""Decision 301 review (FIX-HACK): prize money flows against the real database.

judged result -> payout -> corrected result published -> no second payout, a recovery opened and notified;
the reversal block; the verified-claim rule and maker-checker (with the single-finance exemption);
currency precision; part-paid pool; prize amount lock.
Written without running (no Docker in the lane); the hack-money `world` fixture is reused as is.
"""
from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from apps.events.judging import payouts, prize_claims, prize_outcomes, prize_reads, prize_shares
from apps.events.judging.definitions_workflow import save_definition
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_definitions import HackathonPrize
from apps.events.judging.models_payouts import HackathonPrizePayout
from apps.events.judging.models_prize_money import HackathonPrizeClaim, HackathonPrizeOutcome, HackathonPrizeShare
from apps.events.judging.models_results import EventAward, EventResultRound
from apps.events.judging.results_workflow import finalize, publish
from tests.events.collab_helpers import make_staff
from tests.hackmoney_local.helpers import command, world  # noqa: F401
from tests.hackmoney_local.prize_helpers import accept_payees, payee, user, winning_award

pytestmark = pytest.mark.django_db(transaction=True)  # a claim prepares its tenant key outside any transaction


@pytest.fixture(autouse=True)
def pii_key(settings):
    from cryptography.fernet import Fernet
    settings.PII_KEY_BROKER = "local"
    settings.PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.PII_SEARCH_HASH_KEY = ""
    from apps.encryption.cache import dek_cache
    dek_cache.clear()


def claim_verified(world, settings, award, members, *, verifier):
    """The leader gives payee details and `verifier` checks them (the real claim flow)."""
    accept_payees(settings, world)
    prize_claims.submit(world.event.pk, award.pk, actor=user(members[0]), data=command(0, **payee()))
    share = HackathonPrizeShare.objects.get(award=award, member_id=members[0])
    claim = HackathonPrizeClaim.objects.get(share=share)
    prize_claims.verify(world.event.pk, share.pk, actor=verifier, data=command(claim.version))
    return share


def record(world, award, *, actor, **fields):
    data = command(0, award_id=award.pk, method="bank_transfer", reference="UTR-1", paid_on="2026-11-05", **fields)
    return payouts.record_payout(world.event.pk, actor=actor, data=data)


def correct_and_publish(world, award, snapshot_id):
    """A result correction (new award rows) naming `snapshot_id` for the same prize, announced."""
    round_ids = list(EventResultRound.objects.filter(result=award.result).values_list("round_id", flat=True))
    result = finalize(world.event.pk, actor=world.manager, correction=True, data=command(
        award.result.version, round_ids=round_ids, integrity_reviewed=True, reason="Judging error",
        awards=[{"prize_id": award.prize_id, "snapshot_id": snapshot_id, "rank": 1}]))
    publish(world.event.pk, actor=world.manager, data=command(result["version"], result_revision_id=result["id"]))
    return EventAward.objects.get(result_id=result["id"])


@pytest.fixture
def paid(world, settings):
    """A verified claim (checked by a second finance person), then the payout recorded by the manager."""
    award, members = winning_award(world, second_member=False)
    checker = make_staff(world.space, username="fin-checker")
    claim_verified(world, settings, award, members, verifier=checker)
    row = record(world, award, actor=world.manager)
    return world, award, members, row


# --- correction after a payout ---------------------------------------------------------------------

def test_a_correction_that_keeps_the_team_never_re_opens_the_paid_prize(paid):
    world, award, members, row = paid
    new_award = correct_and_publish(world, award, award.submission_snapshot_id)
    assert new_award.pk != award.pk
    listed = {entry["id"]: entry for entry in payouts.payable_awards(world.event)}
    assert listed[new_award.pk]["paid"] is True and listed[new_award.pk]["status"] == "paid"
    with pytest.raises(ProgrammeError) as twice:
        record(world, new_award, actor=world.manager)
    assert twice.value.detail["code"] == "payout_exists"
    assert HackathonPrizePayout.objects.filter(kind="payout", reversal__isnull=True).count() == 1
    assert not HackathonPrizeOutcome.objects.filter(kind="recovery_opened").exists()
    assert prize_reads.prize_pool(world.event)["owed"] == Decimal("0.00")


def test_a_correction_that_drops_the_paid_team_opens_a_recovery_and_tells_the_winner(
        paid, monkeypatch, django_capture_on_commit_callbacks):
    world, award, members, row = paid
    sent = []
    monkeypatch.setattr("apps.events.judging.prize_notices.emit", lambda **kw: sent.append(kw))
    other_snapshot = next(pk for pk in world.snapshots if pk != award.submission_snapshot_id)
    with django_capture_on_commit_callbacks(execute=True):
        correct_and_publish(world, award, other_snapshot)
    recovery = HackathonPrizeOutcome.objects.get(kind="recovery_opened")
    assert recovery.payout_id == row["id"] and recovery.amount == Decimal(row["amount"])
    assert [(call["event"], call["recipient"].pk) for call in sent] == [("prize_recovery_opened", members[0])]
    assert "recovery" in sent[0]["rendered"]()["text"].lower()
    # the money stays owed back: the paid amount is not re-opened as owed on the old team's prize
    assert HackathonPrizePayout.objects.filter(pk=row["id"], kind="payout").exists()


def test_a_payout_cannot_be_reversed_while_its_recovery_is_open(paid, monkeypatch):
    world, award, members, row = paid
    monkeypatch.setattr("apps.events.judging.prize_notices.emit", lambda **kw: None)
    other_snapshot = next(pk for pk in world.snapshots if pk != award.submission_snapshot_id)
    correct_and_publish(world, award, other_snapshot)
    listed, _awards = payouts.listing(world.event.pk, actor=world.manager)
    assert next(entry for entry in listed if entry["id"] == row["id"])["allowed_actions"] == []
    with pytest.raises(ProgrammeError) as blocked:
        payouts.reverse_payout(world.event.pk, row["id"], actor=world.manager, data=command(0, reason="Wrong account"))
    assert blocked.value.detail["code"] == "recovery_open"
    opened = HackathonPrizeOutcome.objects.get(kind="recovery_opened")
    prize_outcomes.resolve_recovery(world.event.pk, opened.pk, actor=world.manager, data=command(
        0, outcome="waived", note="Agreed with the team", happened_on="2026-11-06"))
    reversal = payouts.reverse_payout(world.event.pk, row["id"], actor=world.manager, data=command(0, reason="Wrong account"))
    assert reversal["kind"] == "reversal"


# --- verified claim and maker-checker ---------------------------------------------------------------

def test_a_payout_needs_a_verified_claim(world, settings):
    award, members = winning_award(world, second_member=False)
    with pytest.raises(ProgrammeError) as none_given:
        record(world, award, actor=world.manager)
    assert none_given.value.detail["code"] == "claim_not_verified"
    accept_payees(settings, world)
    prize_claims.submit(world.event.pk, award.pk, actor=user(members[0]), data=command(0, **payee()))
    with pytest.raises(ProgrammeError) as unverified:
        record(world, award, actor=world.manager)
    assert unverified.value.detail["code"] == "claim_not_verified"


def test_the_verifier_cannot_record_the_payout_when_a_second_finance_person_exists(world, settings):
    award, members = winning_award(world, second_member=False)
    second = make_staff(world.space, username="fin-second")
    claim_verified(world, settings, award, members, verifier=world.manager)
    with pytest.raises(ProgrammeError) as same:
        record(world, award, actor=world.manager)
    assert same.value.detail["code"] == "same_person_verified"
    assert record(world, award, actor=second)["kind"] == "payout"  # the second person may


def test_a_single_finance_person_may_verify_and_record(world, settings):
    award, members = winning_award(world, second_member=False)
    claim_verified(world, settings, award, members, verifier=world.manager)
    assert record(world, award, actor=world.manager)["kind"] == "payout"


# --- precision, reference, pool, lock ------------------------------------------------------------------

def test_an_amount_finer_than_the_currency_and_a_blank_reference_are_refused(world, settings):
    award, members = winning_award(world, second_member=False)
    claim_verified(world, settings, award, members, verifier=make_staff(world.space, username="fin-precision"))
    with pytest.raises(ValidationError):
        record(world, award, actor=world.manager, amount="10.005")  # a thousandth of a rupee does not exist
    with pytest.raises(ValidationError):
        payouts.record_payout(world.event.pk, actor=world.manager, data=command(
            0, award_id=award.pk, method="cash", reference="  ", paid_on="2026-11-06"))
    assert not HackathonPrizePayout.objects.exists()


def test_the_pool_counts_a_part_paid_prize_by_what_is_still_unpaid(world, settings):
    award, members = winning_award(world)  # two members
    rows = [{"member_id": members[0], "amount": "600.00"}, {"member_id": members[1], "amount": "400.00"}]
    prize_shares.record_split(world.event.pk, award.pk, actor=world.manager, data=command(0, shares=rows))
    checker = make_staff(world.space, username="fin-pool")
    claim_verified(world, settings, award, members, verifier=checker)
    record(world, award, actor=world.manager, recipient_id=members[0])
    assert prize_reads.prize_pool(world.event)["owed"] == Decimal("400.00")


def test_a_prize_amount_and_kind_are_fixed_once_a_payout_exists(paid):
    world, award, members, row = paid
    prize = HackathonPrize.objects.get(pk=award.prize_id)
    with pytest.raises(ProgrammeError) as locked:
        save_definition(world.event.pk, actor=world.manager, kind="prizes", object_id=prize.pk,
                        data=command(prize.version, amount_per_winner="5000.00"))
    assert locked.value.status_code == 409 and locked.value.detail["code"] == "prize_locked"
    with pytest.raises(ProgrammeError):
        save_definition(world.event.pk, actor=world.manager, kind="prizes", object_id=prize.pk,
                        data=command(prize.version, kind="item"))
