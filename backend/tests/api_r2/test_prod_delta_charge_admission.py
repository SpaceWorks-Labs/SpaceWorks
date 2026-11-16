"""PROD-DELTA: settling a debt cannot depend on choosing an inaccessible handle."""

import pytest

from tests.api_r2.test_restricted_own_charges_0120 import _phone, _restrict, _web
from tests.payments.test_borrower_charge_visibility import _borrower, _loan_deposit
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.handle_gate]


@pytest.mark.parametrize("state", ["active", "restricted", "suspended"])
@pytest.mark.parametrize("native", [False, True])
def test_handleless_charge_checkout_keeps_the_narrow_restricted_exception(monkeypatch, state, native):
    space = make_space(f"prod-delta-handle-{state}-{native}")
    borrower = _borrower(space, f"prod-delta-handle-{state}-{native}-user")
    debt = _loan_deposit(space, borrower)
    client = _phone(borrower, space) if native else _web(borrower)
    monkeypatch.setattr("apps.makerspaces.public_profile_handles.has_handle", lambda _user: False)
    monkeypatch.setattr("apps.makerspaces.public_profile_handles.in_release_cooldown", lambda _user: False)
    _restrict(borrower, state)
    response = client.post(f"/api/v1/member/makerspaces/{space.pk}/payments/{debt.pk}/checkout")
    if state == "active":
        assert response.status_code == 403 and response.data["code"] == "handle_required"
    else:
        assert response.status_code == 503 and response.data["code"] == "payments_unavailable"
        denied = client.post("/api/v1/member/profile/handle", {"handle": "cannot-change"})
        assert denied.status_code == 401 and denied.data["code"] == f"account_{state}"


@pytest.mark.parametrize("state", ["active", "restricted", "suspended"])
def test_account_only_native_borrower_can_select_their_money_only_summary(state):
    space = make_space(f"prod-delta-summary-{state}")
    borrower = _borrower(space, f"prod-delta-summary-{state}-user")
    _loan_deposit(space, borrower)
    client = _phone(borrower, space)
    _restrict(borrower, state)
    response = client.get(f"/api/v1/member/makerspaces/{space.pk}/my-usage")
    assert response.status_code == 200, response.data
    assert response.data["usage_available"] is False and "payments" in response.data
    assert "loans" not in response.data
    other = make_space(f"prod-delta-summary-other-{state}")
    assert client.get(f"/api/v1/member/makerspaces/{other.pk}/my-usage").status_code == 403
