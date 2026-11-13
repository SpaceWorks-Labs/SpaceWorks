"""Hack-money G4 forfeits, G5/G8 fulfilment and the prize pool, G6 reads and report, G16 recoveries."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.http import Http404
from django.utils import timezone

from apps.events.judging import options, prize_outcomes, prize_reads
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_prize_money import HackathonPrizeOutcome
from apps.payments.models_ledger_entries import LedgerEntry
from tests.hackmoney_local.helpers import command, enable, world  # noqa: F401
from tests.hackmoney_local.prize_helpers import pay, user, winning_award

pytestmark = pytest.mark.django_db


def fulfil(world, award, **fields):
    data = command(0, **{"method": "handed_over", "happened_on": "2026-11-05", **fields})
    return prize_outcomes.fulfil(world.event.pk, award.pk, actor=world.manager, data=data)


def claim_window(world, monkeypatch, days, *, closed):
    """Announcements are append-only, so a closed window is a deadline in the past."""
    from apps.events.judging import prize_claims
    options.update(world.event.pk, actor=world.manager, data=command(0, prize_claim_days=days))
    if closed:
        monkeypatch.setattr(prize_claims, "claim_deadline", lambda event: timezone.now() - timedelta(days=1))


# G5 / G8 ----------------------------------------------------------------------------------------

def test_a_non_cash_prize_is_fulfilled_without_any_ledger_entry(world):
    award, _members = winning_award(world, kind="item", value_text="Pi kit", second_member=False)
    before = LedgerEntry.objects.count()
    row = fulfil(world, award, reference="Courier 123")
    assert row["kind"] == "fulfilled" and row["ledger_entry_id"] is None
    assert LedgerEntry.objects.count() == before
    with pytest.raises(ProgrammeError) as twice:
        fulfil(world, award)
    assert twice.value.detail["code"] == "already_settled"


def test_a_sponsor_direct_prize_is_recorded_as_sponsor_paid_never_as_an_expense(world):
    award, _members = winning_award(world, funding="sponsor_direct", second_member=False)
    with pytest.raises(ProgrammeError) as payout:
        pay(world, award)
    assert payout.value.detail["code"] == "sponsor_direct"
    assert fulfil(world, award, method="sponsor_paid")["kind"] == "sponsor_paid"


def test_a_cash_prize_the_space_pays_cannot_be_marked_fulfilled(world):
    award, _members = winning_award(world, second_member=False)
    with pytest.raises(ProgrammeError) as cash:
        fulfil(world, award)
    assert cash.value.detail["code"] == "cash_prize"


def test_outcome_rows_are_append_only(world):
    award, _members = winning_award(world, kind="perk", second_member=False)
    row = HackathonPrizeOutcome.objects.get(pk=fulfil(world, award)["id"])
    row.note = "edited"
    with pytest.raises(RuntimeError):
        row.save()


# G4 forfeit ---------------------------------------------------------------------------------------

def test_forfeit_needs_a_closed_claim_window_and_has_no_ledger_effect(world, monkeypatch):
    award, _members = winning_award(world, second_member=False)
    with pytest.raises(ProgrammeError) as none:
        prize_outcomes.forfeit(world.event.pk, award.pk, actor=world.manager, data=command(0, note="No reply"))
    assert none.value.detail["code"] == "claim_window_open"
    claim_window(world, monkeypatch, 14, closed=True)
    before = LedgerEntry.objects.count()
    row = prize_outcomes.forfeit(world.event.pk, award.pk, actor=world.manager, data=command(0, note="No reply"))
    assert row["kind"] == "forfeited" and LedgerEntry.objects.count() == before
    with pytest.raises(ProgrammeError) as settled:
        pay(world, award)
    assert settled.value.detail["code"] == "already_settled"
    assert prize_reads.prize_pool(world.event)["owed"] == Decimal("0.00")


# G16 recovery -----------------------------------------------------------------------------------------

def test_disqualifying_a_paid_winner_opens_a_recovery_and_never_charges(world):
    from apps.events.submissions.entry_fees import on_disqualified
    from apps.events.submissions.models_projects import SubmissionSnapshot
    from apps.payments.models import Payment
    award, _members = winning_award(world, second_member=False)
    payout = pay(world, award)
    project = SubmissionSnapshot.objects.get(pk=award.submission_snapshot_id).submission
    payments_before = Payment.objects.count()
    on_disqualified(event=world.event, project=project, actor=world.manager)
    opened = HackathonPrizeOutcome.objects.get(kind="recovery_opened", payout_id=payout["id"])
    assert opened.amount == Decimal("1000.00") and Payment.objects.count() == payments_before
    on_disqualified(event=world.event, project=project, actor=world.manager)  # idempotent
    assert HackathonPrizeOutcome.objects.filter(kind="recovery_opened").count() == 1


def test_a_repaid_recovery_writes_one_ledger_receipt_and_a_waiver_needs_a_reason(world):
    from rest_framework.exceptions import ValidationError
    from apps.events.submissions.entry_fees import on_disqualified
    from apps.events.submissions.models_projects import SubmissionSnapshot
    award, _members = winning_award(world, second_member=False)
    pay(world, award)
    project = SubmissionSnapshot.objects.get(pk=award.submission_snapshot_id).submission
    on_disqualified(event=world.event, project=project, actor=world.manager)
    opened = HackathonPrizeOutcome.objects.get(kind="recovery_opened")
    with pytest.raises(ValidationError):
        prize_outcomes.resolve_recovery(world.event.pk, opened.pk, actor=world.manager,
                                        data=command(0, outcome="waived", happened_on="2026-11-06"))
    row = prize_outcomes.resolve_recovery(world.event.pk, opened.pk, actor=world.manager, data=command(
        0, outcome="repaid", method="bank_transfer", reference="RET-1", happened_on="2026-11-06"))
    entry = LedgerEntry.objects.get(pk=row["ledger_entry_id"])
    assert (entry.kind, entry.category, entry.amount) == ("receipt", "prize_recovery", Decimal("1000.00"))
    with pytest.raises(ProgrammeError) as twice:
        prize_outcomes.resolve_recovery(world.event.pk, opened.pk, actor=world.manager, data=command(
            0, outcome="waived", note="Gave up", happened_on="2026-11-07"))
    assert twice.value.detail["code"] == "already_resolved"


def test_only_payment_recorders_or_the_event_manager_record_outcomes(world):
    award, _members = winning_award(world, kind="item", second_member=False)
    with pytest.raises(Http404):
        prize_outcomes.fulfil(world.event.pk, award.pk, actor=world.judges[0],
                              data=command(0, method="handed_over", happened_on="2026-11-05"))


# G6 reads, G8 pool, report ------------------------------------------------------------------------

def test_public_prizes_404_until_the_organiser_shows_them_and_never_name_a_winner(world):
    award, _members = winning_award(world, second_member=False)
    with pytest.raises(Http404):
        prize_reads.public_prizes(world.event)
    options.update(world.event.pk, actor=world.manager, data=command(0, show_prize_amounts=True))
    rows = prize_reads.public_prizes(world.event)
    assert rows[0]["amount_per_winner"] == Decimal("1000.00")
    assert not {"recipient_id", "member_id", "winner"} & set(rows[0])


def test_my_prizes_lists_the_members_award_with_status_and_claim_action(world):
    award, members = winning_award(world, second_member=False)
    rows = prize_reads.my_prizes(user(members[0]), world.space.pk)
    assert rows[0]["award_id"] == award.pk and rows[0]["status"] == "owed"
    assert "claim" in rows[0]["allowed_actions"] and rows[0]["tax_id_requested"] is False
    pay(world, award)
    paid = prize_reads.my_prizes(user(members[0]), world.space.pk)[0]
    assert paid["status"] == "paid" and paid["my_payout"]["gross"] == "1000.00" and paid["allowed_actions"] == []


def test_prize_pool_counts_earmarked_sponsorship_and_payouts(world):
    from apps.payments.donations import sponsors
    from apps.payments.donations.models_sponsors import Sponsor
    from apps.payments.models import Payment
    enable(world, "charges.donations")  # sponsor money is recorded only while the donations charge family is on
    award, _members = winning_award(world, second_member=False)
    sponsor = Sponsor.objects.create(makerspace=world.space, name="Acme")
    charge, payment = sponsors.raise_charge(sponsor, actor=world.manager, amount=Decimal("5000.00"),
                                            event_id=world.event.pk, earmark="prize_pool")
    Payment.objects.filter(pk=payment.pk).update(status="paid_offline")
    pay(world, award)
    pool = prize_reads.prize_pool(world.event)
    assert pool["sponsor_funded"] == Decimal("5000.00") and pool["paid_gross"] == Decimal("1000.00")
    assert pool["owed"] == Decimal("0.00") and charge.earmark == "prize_pool"


def test_a_prize_pool_earmark_needs_an_event_in_this_space(world):
    from apps.payments.donations import sponsors
    from apps.payments.donations.gates import DonationRefused
    from apps.payments.donations.models_sponsors import Sponsor
    enable(world, "charges.donations")  # so the refusal below is the earmark rule, not "charges_off"
    sponsor = Sponsor.objects.create(makerspace=world.space, name="Acme")
    with pytest.raises(DonationRefused) as refused:
        sponsors.raise_charge(sponsor, actor=world.manager, amount=Decimal("10.00"), event_id=999999,
                              earmark="prize_pool")
    assert refused.value.detail["code"] != "charges_off"


def test_prizes_owed_report_lists_unsettled_awards_without_naming_anyone(world):
    from apps.operations.reports_prizes_owed import build_prizes_owed
    award, _members = winning_award(world, second_member=False)
    result = build_prizes_owed(world.space.pk)
    row = next(item for item in result.records if item["event_id"] == world.event.pk)
    assert row["status"] == "owed" and row["amount_outstanding"] == Decimal("1000.00")
    assert not {"recipient_id", "member_id", "name", "email"} & set(row)
    pay(world, award)
    assert not [item for item in build_prizes_owed(world.space.pk).records if item["event_id"] == world.event.pk]
