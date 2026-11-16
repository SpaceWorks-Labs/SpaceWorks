"""Payments audit 0.12.0, sub-lane D: the member's owe -> pay -> receipt chain.

D-4  "Outstanding" sums exactly what the Payments list shows (member scope, not a raw filter).
D-6  While an "I paid" claim waits for staff, no hosted page is handed out again (list, member
     checkout and pay-link checkout), so the same debt cannot be paid twice.
B-7  A pending donation is an unfinished gift, never counted as owed; it stays in history.
"""

from tests.payments.membership_rows import community_membership
from datetime import date
from decimal import Decimal
from unittest import mock

import pytest

from apps.makerspaces.member_dashboard_service import membership_dues
from apps.makerspaces.models import MakerspaceMembership
from apps.payments.models import Payment, PaymentClaim
from tests.l5_local.helpers import client, dues, setup

pytestmark = pytest.mark.django_db

LIVE_URL = "https://checkout.example.test/session/live"


def _history(user, space):
    return client(user).get(f"/api/v1/member/makerspaces/{space.pk}/payments")


def _with_live_page(payment):
    Payment.objects.filter(pk=payment.pk).update(checkout_url=LIVE_URL, external_order_id=f"order-{payment.pk}")
    payment.refresh_from_db()
    return payment


def _claim(payer, space, payment):
    return client(payer).post(f"/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/paid-claim",
                              {"reference": "UTR123456789", "paid_on": date.today().isoformat()}, format="json")


def test_outstanding_matches_the_member_list_for_the_same_currency():
    space, _manager, payer = setup("d4-outstanding")
    payment = dues(space, payer, "120.00", currency="usd")
    membership = community_membership(space, payment.member)
    listed = [row for row in _history(payment.member, space).json() if row["status"] == "pending"]
    total = sum(Decimal(row["amount"]) for row in listed if row["currency"] == "usd")
    assert membership_dues(membership)["outstanding_by_currency"] == {"usd": str(total)}


def test_outstanding_uses_the_member_payment_scope():
    """A row the member scope hides (claim-local restriction etc.) must not be counted either."""
    space, _manager, payer = setup("d4-scope")
    payment = dues(space, payer, "40.00", currency="usd")
    membership = community_membership(space, payment.member)
    with mock.patch("apps.payments.member_scope.member_payment_queryset",
                    return_value=Payment.objects.none()) as scoped:
        assert membership_dues(membership)["outstanding_by_currency"] == {}
    scoped.assert_called_once_with(payment.member, space.pk)


def test_a_live_page_is_hidden_from_the_list_while_an_i_paid_claim_waits():
    space, _manager, payer = setup("d6-list", "billing.offline_claims")
    payment = _with_live_page(dues(space, payer))
    assert _history(payment.member, space).json()[0]["checkout_url"] == LIVE_URL
    assert _claim(payment.member, space, payment).status_code == 201
    row = _history(payment.member, space).json()[0]
    assert row["checkout_url"] == ""
    assert row["offline_collection"]["claim"]["status"] in PaymentClaim.OPEN_STATUSES


def test_member_checkout_refuses_a_second_payment_while_a_claim_waits():
    space, _manager, payer = setup("d6-checkout", "billing.offline_claims")
    payment = _with_live_page(dues(space, payer))
    assert _claim(payment.member, space, payment).status_code == 201
    response = client(payment.member).post(
        f"/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/checkout")
    assert response.status_code == 409
    assert response.json()["code"] == "payment_settlement_pending"
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING


def test_member_checkout_still_hands_back_the_live_page_without_a_claim():
    space, _manager, payer = setup("d6-no-claim")
    payment = _with_live_page(dues(space, payer))
    response = client(payment.member).post(
        f"/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/checkout")
    assert response.status_code == 200 and response.json()["checkout_url"] == LIVE_URL


def test_pay_link_checkout_refuses_a_second_payment_while_a_claim_waits():
    from apps.payments.views_pay_links import live_link  # noqa: F401  (route present)

    space, _manager, payer = setup("d6-paylink", "billing.offline_claims", "billing.pay_links")
    payment = _with_live_page(dues(space, payer))
    assert _claim(payment.member, space, payment).status_code == 201
    link = mock.Mock(payment=payment, created_by=payment.created_by)
    with mock.patch("apps.payments_rail.views_pay_link_checkout.live_link", return_value=link), \
            mock.patch("apps.payments_rail.views_pay_link_checkout.online_payments_enabled_for", return_value=True):
        response = client(payment.member).post("/api/v1/public/pay/any-token/checkout")
    assert response.status_code == 409
    assert response.json()["code"] == "payment_settlement_pending"


def _pending_gift(space_slug):
    from tests.payments.test_audit_0120_seams_events_shop_membership_donations import _donor, _gift_space
    from apps.payments.donations.services import create_gift

    space = _gift_space(space_slug)
    donor = _donor(space, f"{space_slug}-giver")
    _gift, payment = create_gift(space, donor, amount=Decimal("50.00"))
    return space, donor.account, payment


def test_a_pending_donation_is_not_counted_as_owed_but_stays_in_history():
    space, giver, gift = _pending_gift("b7-gift")
    assert gift.status == Payment.Status.PENDING
    membership = community_membership(space, giver)
    assert membership_dues(membership)["outstanding_by_currency"] == {}
    listed = _history(giver, space).json()
    assert [row["id"] for row in listed if row["subject_type"] == "donation"] == [gift.pk]


def test_a_pending_donation_is_not_in_the_usage_outstanding_total():
    from apps.makerspaces.member_usage_service import payment_usage

    space, giver, _gift = _pending_gift("b7-usage")
    usage = payment_usage(space, giver)
    assert usage["outstanding_by_currency"] == {}
