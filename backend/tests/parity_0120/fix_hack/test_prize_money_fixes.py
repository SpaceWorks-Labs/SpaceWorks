"""Decision 301 review (FIX-HACK): double-pay lineage, maker-checker, precision, reversal block, notices.

Not run by the author (no Docker in the lane); they stub the seams so no database fixtures are needed.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from apps.events.judging import payout_checks, prize_lineage, prize_precision
from apps.events.judging.errors import ProgrammeError


# --- double payment: payouts bind to (prize, team), never to one award row ---------------------------

class _Awards(list):
    def exclude(self, **kw):
        return _Awards(a for a in self if a.pk != kw["pk"])


def _award(pk, prize_id, snapshot_id):
    return SimpleNamespace(pk=pk, prize_id=prize_id, submission_snapshot_id=snapshot_id,
                           result=SimpleNamespace(event_id=1))


def _teams(monkeypatch, teams):
    monkeypatch.setattr(prize_lineage, "runtime",
                        lambda: SimpleNamespace(snapshot=lambda i: SimpleNamespace(team_id=teams[i])))


def test_lineage_joins_awards_of_the_same_prize_and_team_across_revisions(monkeypatch):
    rev1, rev2, other_team = _award(1, 5, 10), _award(2, 5, 11), _award(3, 5, 12)
    _teams(monkeypatch, {10: 100, 11: 100, 12: 200})
    monkeypatch.setattr(prize_lineage.EventAward, "objects",
                        SimpleNamespace(filter=lambda **kw: _Awards([rev1, rev2, other_team])))
    assert prize_lineage.lineage_ids(rev2) == [2, 1]  # the corrected award sees the paid one


def test_correction_opens_a_recovery_only_for_a_paid_team_that_lost_the_prize(monkeypatch):
    kept = _award(9, 5, 20)
    paid_kept = SimpleNamespace(pk=1, prize_id=5, award=_award(2, 5, 11), recipient_id=7)
    paid_lost = SimpleNamespace(pk=2, prize_id=5, award=_award(3, 5, 12), recipient_id=8)
    _teams(monkeypatch, {20: 100, 11: 100, 12: 200})

    class _Payouts:
        def filter(self, **kw): return self
        def select_related(self, *a): return self
        def order_by(self, *a): return [paid_kept, paid_lost]

    monkeypatch.setattr(prize_lineage.HackathonPrizePayout, "objects", _Payouts())
    monkeypatch.setattr(prize_lineage.HackathonPrizeOutcome, "objects",
                        SimpleNamespace(filter=lambda **kw: SimpleNamespace(exists=lambda: False)))
    opened = []
    monkeypatch.setattr("apps.events.judging.prize_outcomes.open_recovery_row",
                        lambda **kw: opened.append(kw["payout"].pk) or kw["payout"])
    prize_lineage.recoveries_for_correction_locked(event=SimpleNamespace(), actor=None, new_awards=[kept])
    assert opened == [2]


# --- precision -------------------------------------------------------------------------------------

@pytest.mark.parametrize("code, amount, ok", [
    ("inr", "10.50", True), ("inr", "10.505", False), ("jpy", "100", True), ("jpy", "100.5", False),
    ("kwd", "0.005", True), ("usd", "0.005", False),
])
def test_amounts_must_fit_the_currency_minor_unit(monkeypatch, code, amount, ok):
    monkeypatch.setattr("apps.events.judging.options.currency", lambda space: code)
    if ok:
        prize_precision.require_precision("amount", Decimal(amount), object())
    else:
        with pytest.raises(ValidationError):
            prize_precision.require_precision("amount", Decimal(amount), object())


# --- verified claim and maker-checker -------------------------------------------------------------------

class _Claims:
    def __init__(self, claim): self.claim = claim
    def select_related(self, *a): return self
    def filter(self, **kw): return self
    def order_by(self, *a): return self
    def first(self): return self.claim


def _claim(verified_by=None, verified=True):
    return SimpleNamespace(submitted_at=date.today(), cleared_at=None,
                           verified_at=date.today() if verified else None, verified_by_id=verified_by)


def _wire(monkeypatch, claim, finance):
    monkeypatch.setattr(payout_checks, "claims_flow", lambda event: True)
    monkeypatch.setattr(payout_checks.HackathonPrizeClaim, "objects", _Claims(claim))
    monkeypatch.setattr("apps.events.judging.payout_split.lineage_shares",
                        lambda award: SimpleNamespace(filter=lambda **kw: []))
    monkeypatch.setattr(payout_checks, "finance_ids", lambda makerspace_id: set(finance))


EVENT = SimpleNamespace(makerspace_id=1)


def test_an_unverified_or_missing_claim_blocks_the_payout(monkeypatch):
    _wire(monkeypatch, None, {1, 2})
    with pytest.raises(ProgrammeError) as caught:
        payout_checks.require_verified_claim(EVENT, object(), 7, SimpleNamespace(pk=1))
    assert caught.value.detail["code"] == "claim_not_verified"
    _wire(monkeypatch, _claim(verified=False), {1, 2})
    with pytest.raises(ProgrammeError):
        payout_checks.require_verified_claim(EVENT, object(), 7, SimpleNamespace(pk=1))


def test_the_verifier_cannot_record_the_payout_when_a_second_finance_person_exists(monkeypatch):
    _wire(monkeypatch, _claim(verified_by=1), {1, 2})
    with pytest.raises(ProgrammeError) as caught:
        payout_checks.require_verified_claim(EVENT, object(), 7, SimpleNamespace(pk=1))
    assert caught.value.detail["code"] == "same_person_verified"
    payout_checks.require_verified_claim(EVENT, object(), 7, SimpleNamespace(pk=2))  # the second person may


def test_a_single_finance_person_may_do_both(monkeypatch):
    _wire(monkeypatch, _claim(verified_by=1), {1})
    payout_checks.require_verified_claim(EVENT, object(), 7, SimpleNamespace(pk=1))


def test_no_claim_flow_means_no_claim_needed(monkeypatch):
    monkeypatch.setattr(payout_checks, "claims_flow", lambda event: False)
    payout_checks.require_verified_claim(EVENT, object(), 7, SimpleNamespace(pk=1))


# --- inputs ---------------------------------------------------------------------------------------------

def test_a_payout_needs_a_non_blank_reference():
    from apps.events.judging.serializers_l21b import PayoutInput
    base = {"operation_id": "6f0c2d2e-0f4c-4a5b-9c1e-0a1b2c3d4e5f", "expected_version": 0, "award_id": 1,
            "method": "cash", "paid_on": "2026-01-01"}
    assert not PayoutInput(data={**base, "reference": "  "}).is_valid()
    assert not PayoutInput(data=base).is_valid()
    assert PayoutInput(data={**base, "reference": "UTR1"}).is_valid()


def test_a_share_below_a_cent_is_accepted_by_the_input():
    from apps.events.judging.serializers_prize import SplitInput
    data = {"operation_id": "6f0c2d2e-0f4c-4a5b-9c1e-0a1b2c3d4e5f", "expected_version": 0,
            "shares": [{"member_id": 1, "amount": "0.005"}]}
    assert SplitInput(data=data).is_valid()


# --- notices ----------------------------------------------------------------------------------------------

def test_prize_step_notices_are_in_the_catalogue_and_gated_by_the_payout_capability():
    from apps.integrations.notification_catalog import FEATURE_EVENTS
    from apps.integrations.notification_catalog_sources import EVENT_SOURCES
    from apps.integrations.notification_enums import NotificationFeature as F
    for name in ("prize_split_proposed", "prize_claim_verified", "prize_forfeited", "prize_recovery_opened"):
        assert name in FEATURE_EVENTS[F.EVENTS]
        assert EVENT_SOURCES[(F.EVENTS, name)] == "events.prize_payouts"


def test_the_payout_notice_names_the_net_amount_with_its_currency():
    from apps.events.judging.payout_notices import _paid_text
    payout = SimpleNamespace(currency="inr", amount=Decimal("10000.00"), tds_amount=Decimal("1000.00"), net_amount=None)
    assert _paid_text(payout) == "INR 9000.00"


def test_unknown_prize_notice_is_refused():
    from apps.events.judging.prize_notices import prize_step_notice
    with pytest.raises(ValueError):
        prize_step_notice(SimpleNamespace(), 1, "nope", 1)


def test_reveal_requires_a_recent_reauthentication(monkeypatch):
    from apps.accounts.reauthentication import RecentAuthenticationRequired
    from apps.events.judging import views_prize
    monkeypatch.setattr(views_prize, "require_full_session", lambda request: None)

    def refuse(request):
        raise RecentAuthenticationRequired()

    monkeypatch.setattr(views_prize, "require_recent_reauth", refuse)
    with pytest.raises(RecentAuthenticationRequired):
        views_prize.PrizeClaimReveal().post(SimpleNamespace(user=SimpleNamespace(pk=1), data={}), 1, 7)
