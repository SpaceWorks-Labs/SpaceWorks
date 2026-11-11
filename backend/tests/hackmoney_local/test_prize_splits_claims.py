"""Hack-money G3 (splits), G4 (claims), #181 G7 (prize tax, record only): nothing here moves money."""
from decimal import Decimal

import pytest
from django.http import Http404
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.events.judging import prize_claims, prize_shares
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_payouts import HackathonPrizePayout
from apps.events.judging.models_prize_money import HackathonPrizeClaim, HackathonPrizeShare
from apps.events.judging.prize_tax import mask_pan, proposed_tds
from apps.payments.models_ledger_entries import LedgerEntry
from tests.hackmoney_local.helpers import command, world  # noqa: F401
from tests.hackmoney_local.prize_helpers import accept_payees, pay, payee, tax_on, user, winning_award

pytestmark = pytest.mark.django_db


def split(world, award, members, amounts=("600.00", "400.00")):
    leader = user(members[0])
    rows = [{"member_id": pk, "amount": amount} for pk, amount in zip(members, amounts)]
    return prize_shares.propose(world.event.pk, award.pk, actor=leader, data=command(0, shares=rows))


# G3 -------------------------------------------------------------------------------------------

def test_with_no_split_the_l21b_default_pays_the_leader_once(world):
    award, members = winning_award(world)
    row = pay(world, award)
    # boundary.command now answers money in its JSON form (R3 fix: receipts are a plain JSONField).
    assert row["recipient_id"] == members[0] and Decimal(row["amount"]) == Decimal("1000.00")
    with pytest.raises(ProgrammeError) as twice:
        pay(world, award)
    assert twice.value.detail["code"] == "payout_exists"


def test_leader_proposes_member_confirms_and_each_share_is_its_own_payout(world):
    award, members = winning_award(world)
    result = split(world, award, members)
    shares = {row["member_id"]: row for row in result["shares"]}
    assert shares[members[0]]["state"] == "confirmed" and shares[members[1]]["state"] == "proposed"
    with pytest.raises(ProgrammeError) as unconfirmed:
        pay(world, award, recipient=members[1])
    assert unconfirmed.value.detail["code"] == "share_not_confirmed"
    mate = shares[members[1]]
    prize_shares.respond(world.event.pk, mate["id"], actor=user(members[1]), data=command(mate["version"]), accept=True)
    first = pay(world, award, recipient=members[0])
    second = pay(world, award, recipient=members[1])
    assert (first["amount"], second["amount"]) == (Decimal("600.00"), Decimal("400.00"))
    assert LedgerEntry.objects.filter(pk__in=[first["ledger_entry_id"], second["ledger_entry_id"]]).count() == 2


def test_a_split_never_exceeds_the_prize_and_only_the_leader_proposes(world):
    award, members = winning_award(world)
    with pytest.raises(ValidationError):
        split(world, award, members, amounts=("700.00", "400.00"))
    with pytest.raises(ProgrammeError) as other:
        prize_shares.propose(world.event.pk, award.pk, actor=user(members[1]),
                             data=command(0, shares=[{"member_id": members[1], "amount": "10.00"}]))
    assert other.value.detail["code"] == "leader_required"


def test_staff_record_a_confirmed_split_and_it_is_fixed_once_paid(world):
    award, members = winning_award(world)
    rows = [{"member_id": members[0], "amount": "500.00"}, {"member_id": members[1], "amount": "500.00"}]
    result = prize_shares.record_split(world.event.pk, award.pk, actor=world.manager, data=command(0, shares=rows))
    assert {row["state"] for row in result["shares"]} == {"confirmed"}
    pay(world, award, recipient=members[1])
    with pytest.raises(ProgrammeError) as fixed:
        prize_shares.record_split(world.event.pk, award.pk, actor=world.manager, data=command(0, shares=rows))
    assert fixed.value.detail["code"] == "payout_exists"


def test_a_non_cash_or_sponsor_paid_prize_cannot_be_split_or_paid(world):
    award, members = winning_award(world, kind="item", value_text="Raspberry Pi kit")
    with pytest.raises(ProgrammeError) as kind:
        pay(world, award)
    assert kind.value.detail["code"] == "non_cash_prize"
    with pytest.raises(ProgrammeError):
        split(world, award, members)


# G4 / G7 --------------------------------------------------------------------------------------

def test_a_claim_is_encrypted_masked_and_never_audited_in_full(world, settings):
    accept_payees(settings, world)
    award, members = winning_award(world, second_member=False)
    leader = user(members[0])
    claim = prize_claims.submit(world.event.pk, award.pk, actor=leader, data=command(0, **payee(pan="ABCDE1234F")))
    assert claim["state"] == "submitted" and claim["pan_masked"].endswith("234F") and "asha@okbank" not in str(claim)
    row = HackathonPrizeClaim.objects.get(share__award=award)
    assert row.share.amount == Decimal("1000.00")  # the leader's default single share
    audit = AuditLog.objects.filter(action="event.prize.claim_submitted").latest("pk")
    assert "ABCDE1234F" not in str(audit.meta) and "asha" not in str(audit.meta)


def test_a_payee_pair_the_space_does_not_accept_is_refused(world, settings):
    accept_payees(settings, world, pairs=(("IN", "bank_transfer"),))
    award, members = winning_award(world, second_member=False)
    with pytest.raises(ProgrammeError):
        prize_claims.submit(world.event.pk, award.pk, actor=user(members[0]), data=command(0, **payee()))


def test_a_bad_pan_is_refused_and_a_pan_is_optional(world, settings):
    accept_payees(settings, world)
    award, members = winning_award(world, second_member=False)
    with pytest.raises(ValidationError):
        prize_claims.submit(world.event.pk, award.pk, actor=user(members[0]), data=command(0, **payee(pan="1234")))
    assert prize_claims.submit(world.event.pk, award.pk, actor=user(members[0]),
                               data=command(0, **payee()))["pan_masked"] == ""


def test_finance_reveal_is_audited_with_its_reason_and_paying_clears_the_routing(world, settings):
    accept_payees(settings, world)
    award, members = winning_award(world, second_member=False)
    claim = prize_claims.submit(world.event.pk, award.pk, actor=user(members[0]), data=command(0, **payee(pan="ABCDE1234F")))
    shown = prize_claims.reveal(world.event.pk, claim["share_id"], actor=world.manager,
                                data=command(claim["version"], reason_code="pay_winner"))
    assert shown["details"]["upi_id"] == "asha@okbank" and shown["pan"] == "ABCDE1234F"
    audit = AuditLog.objects.filter(action="event.prize.claim_revealed").latest("pk")
    assert audit.meta.get("reason_code") == "pay_winner" and "asha" not in str(audit.meta)
    pay(world, award)
    row = HackathonPrizeClaim.objects.get(share_id=claim["share_id"])
    assert row.cleared_at is not None and row.details == "" and row.pan == "ABCDE1234F"  # PAN kept for tax records
    with pytest.raises(Http404):
        prize_claims.reveal(world.event.pk, claim["share_id"], actor=world.manager,
                            data=command(row.version, reason_code="pay_winner"))


def test_a_member_outside_the_winning_team_cannot_claim(world, settings):
    from tests.events.ticketing_helpers import account
    accept_payees(settings, world)
    award, _members = winning_award(world, second_member=False)
    with pytest.raises(Http404):
        prize_claims.submit(world.event.pk, award.pk, actor=account("outsider-claim"), data=command(0, **payee()))


def test_prize_tax_is_off_by_default_and_only_proposes_above_the_threshold(world):
    assert proposed_tds(world.space, Decimal("50000")) == Decimal("0.00")
    tax_on(world)
    assert proposed_tds(world.space, Decimal("10000")) == Decimal("0.00")
    assert proposed_tds(world.space, Decimal("20000")) == Decimal("6000.00")


def test_a_payout_stores_gross_tds_and_net_and_the_ledger_records_the_gross(world):
    tax_on(world)
    award, _members = winning_award(world, amount=Decimal("20000.00"), second_member=False)
    row = pay(world, award)
    assert (row["amount"], row["tds_amount"], row["net_amount"]) == (Decimal("20000.00"), Decimal("6000.00"),
                                                                     Decimal("14000.00"))
    assert LedgerEntry.objects.get(pk=row["ledger_entry_id"]).amount == Decimal("20000.00")
    payout = HackathonPrizePayout.objects.get(pk=row["id"])
    assert payout.net_amount == payout.amount - payout.tds_amount


def test_staff_may_change_the_proposed_tax_but_never_to_the_whole_prize(world):
    tax_on(world)
    award, _members = winning_award(world, amount=Decimal("20000.00"), second_member=False)
    with pytest.raises(ValidationError):
        pay(world, award, tds_amount="20000.00")
    assert pay(world, award, tds_amount="0")["tds_amount"] == Decimal("0.00")


def test_masking_shows_only_the_last_four():
    assert mask_pan("ABCDE1234F").endswith("234F") and "ABCDE" not in mask_pan("ABCDE1234F")


def test_shares_are_unique_per_member(world):
    award, members = winning_award(world)
    split(world, award, members)
    assert HackathonPrizeShare.objects.filter(award=award).count() == 2
