"""Decision 296 review: prize money guards found outside the active judging lane's files.

* the proposed prize tax rounds at the space currency's precision (decision 268), not a fixed cent;
* the full payee reveal and the claims list are session-only (224(c)), like the payout list.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.events.judging import prize_tax


@pytest.mark.parametrize("code, gross, expected", [
    ("INR", "12345.67", Decimal("3703.70")),
    ("JPY", "12345", Decimal("3704")),
    ("KWD", "12345.675", Decimal("3703.703")),
])
def test_proposed_tax_uses_the_currency_precision(monkeypatch, code, gross, expected):
    monkeypatch.setattr(prize_tax, "tax_settings", lambda space: SimpleNamespace(
        prize_tds_enabled=True, prize_tds_threshold=Decimal("10000"), prize_tds_rate=Decimal("30")))
    monkeypatch.setattr("apps.events.judging.options.currency", lambda space: code)
    assert prize_tax.proposed_tds(object(), gross) == expected


def test_proposed_tax_is_zero_below_the_threshold(monkeypatch):
    monkeypatch.setattr(prize_tax, "tax_settings", lambda space: SimpleNamespace(
        prize_tds_enabled=True, prize_tds_threshold=Decimal("10000"), prize_tds_rate=Decimal("30")))
    assert prize_tax.proposed_tds(object(), "100") == Decimal("0")


@pytest.mark.parametrize("view_name", ["PrizeClaimReveal", "PrizeClaims"])
def test_payee_detail_reads_refuse_a_non_interactive_session(monkeypatch, view_name):
    from apps.events.judging import views_prize
    monkeypatch.setattr("apps.payments.payout_session.full_session", lambda request: False)
    view = getattr(views_prize, view_name)()
    request = SimpleNamespace(user=SimpleNamespace(pk=1), data={})
    handler = view.post if view_name == "PrizeClaimReveal" else view.get
    with pytest.raises(PermissionDenied) as caught:
        handler(request, 1, *([7] if view_name == "PrizeClaimReveal" else []))
    assert caught.value.detail["code"] == "full_session_required"
