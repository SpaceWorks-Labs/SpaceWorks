"""Payments on mobile (decision 354), driven through real native device tokens.

Each case is one the web already answers; the phone must get the same answer with the same
authority. Fixtures are the payment suite's own (configured Stripe test keys, a borrower's
loan deposit, a membership-dues charge) so the money rules exercised are the production ones.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.makerspaces.models import MakerspaceMembership
from apps.payments import stripe_client
from apps.payments.models import ManualSettlement, Payment, PaymentDocument
from apps.payments.services_webhooks import apply_webhook_event
from apps.separability import registry
from tests.accounts.account_factories import device_grant, make_staff
from tests.accounts.mfa_helpers import enrolled
from tests.payments.account_helpers import make_payer
from tests.payments.test_borrower_charge_visibility import _borrower, _loan_deposit
from tests.payments.test_documents import settled
from tests.payments.test_manual_settlement_ledger import _dues
from tests.payments.test_mobile_payments import configured_payment, device_client
from tests.return_helpers import make_member, make_space, settlement_payload

pytestmark = pytest.mark.django_db


def _payments(space):
    return f"/api/v1/member/makerspaces/{space.pk}/payments"


def _intent(space, payment):
    return f"{_payments(space)}/{payment.pk}/mobile-intent"


def _member_client(user, space=None):
    """A native member grant; `space` adds the `X-Makerspace-Id` selection header."""
    access, _refresh, _family = issue_device_token_pair(user, device_grant(user))
    client = APIClient()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {access}"}
    if space is not None:
        headers["HTTP_X_MAKERSPACE_ID"] = str(space.pk)
    client.credentials(**headers)
    return client


def _staff_client(space, username, *, header=True):
    """A native STAFF grant: password-issued, MFA-verified, fixed to `space`."""
    person = make_staff(space, username=username)
    grant = device_grant(person, staff_makerspace_id=space.pk)
    row, _secret = enrolled(person)
    person._mfa_verified_version = str(row.version)
    person._mfa_method = "totp"
    access, _refresh, _family = issue_device_token_pair(person, grant)
    client = APIClient()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {access}"}
    if header:
        headers["HTTP_X_MAKERSPACE_ID"] = str(space.pk)
    client.credentials(**headers)
    return client


def _stub_stripe(monkeypatch, intent_id):
    intent = {"id": intent_id, "client_secret": f"{intent_id}_secret_value"}
    created = []
    monkeypatch.setattr(stripe_client, "create_payment_intent",
                        lambda source, *, idempotency_key, **params: created.append(idempotency_key) or intent)
    monkeypatch.setattr(stripe_client, "retrieve_payment_intent", lambda source, found: intent)
    return created


def test_repeat_mobile_intent_returns_the_same_intent_and_creates_it_once(monkeypatch):
    space = make_space("native-pay-repeat")
    member = make_payer("native-pay-repeat-member", space)
    payment = configured_payment(space, member)
    created = _stub_stripe(monkeypatch, "pi_native_repeat")
    client = device_client(member, space)
    first, second = client.post(_intent(space, payment)), client.post(_intent(space, payment))
    assert first.status_code == second.status_code == 200
    assert first.data == second.data and first.data["vendor"] == "stripe"
    assert created == [f"payment-mobile-intent-{payment.pk}"]  # one provider create, Stripe-idempotent key
    assert "sk_test_mobile" not in first.content.decode()


def test_webhook_settles_the_native_intent_and_the_member_list_shows_it_paid(monkeypatch):
    space = make_space("native-pay-webhook")
    member = make_payer("native-pay-webhook-member", space)
    payment = configured_payment(space, member)
    _stub_stripe(monkeypatch, "pi_native_paid")
    client = device_client(member, space)
    assert client.post(_intent(space, payment)).status_code == 200
    pending = client.get(_payments(space))
    assert [row["status"] for row in pending.data if row["id"] == payment.pk] == ["pending"]
    # SCA / 3-D Secure runs inside the provider SDK; the server only learns the outcome here.
    apply_webhook_event(space, {"id": "evt_native_paid", "type": "payment_intent.succeeded",
                                "data": {"object": {"id": "pi_native_paid", "amount_received": 1250,
                                                    "currency": "usd"}}})
    paid = client.get(_payments(space))
    assert [row["status"] for row in paid.data if row["id"] == payment.pk] == ["paid_online"]


def test_account_only_borrower_reads_and_is_told_to_pay_an_unclaimed_charge_at_the_desk():
    space = make_space("native-pay-borrower")
    borrower = _borrower(space, "native-pay-borrower-user")
    deposit = _loan_deposit(space, borrower)  # provider=unclaimed: no gateway behind it
    for client in (_member_client(borrower), _member_client(borrower, space)):
        listed = client.get(_payments(space))
        assert listed.status_code == 200, listed.data
        row = next(item for item in listed.data if item["id"] == deposit.pk)
        assert row["online_payment_available"] is False and row["checkout_url"] == ""
    refused = _member_client(borrower, space).post(_intent(space, deposit))
    assert refused.status_code == 503 and refused.data["code"] == "payments_unavailable"


def test_borrower_selection_stays_narrow():
    space = make_space("native-pay-narrow")
    borrower = _borrower(space, "native-pay-narrow-user")
    _loan_deposit(space, borrower)
    client = _member_client(borrower, space)
    # Owning a charge selects the space for payment routes only, never member activity.
    assert client.get(f"/api/v1/member/makerspaces/{space.pk}/activity").status_code == 403
    stranger = _borrower(space, "native-pay-narrow-stranger")
    assert _member_client(stranger, space).get(_payments(space)).status_code == 403


def test_revoked_member_is_still_refused_on_the_phone():
    space = make_space("native-pay-revoked")
    member = make_member("native-pay-revoked-member", space, membership_role="custom", role="requester")
    MakerspaceMembership.objects.filter(makerspace=space, user=member).update(status="revoked")
    debt = _loan_deposit(space, member)
    client = _member_client(member, space)
    assert client.get(_payments(space)).status_code == 403
    assert client.post(_intent(space, debt)).status_code == 403


def test_rail_switched_off_answers_typed_503_not_500(monkeypatch):
    space = make_space("native-pay-rail-off")
    member = make_payer("native-pay-rail-off-member", space)
    payment = configured_payment(space, member)
    original = registry.runtime_active
    monkeypatch.setattr(registry, "runtime_active", lambda label: label != "payments_rail" and original(label))
    client = device_client(member, space)
    refused = client.post(_intent(space, payment))
    assert refused.status_code == 503 and refused.data["code"] == "payments_unavailable"
    listed = client.get(_payments(space))  # the ledger survives: the debt is still readable
    assert listed.status_code == 200
    assert next(row for row in listed.data if row["id"] == payment.pk)["online_payment_available"] is False


def test_receipt_downloads_with_the_bearer_token_alone():
    space, _staff, payment = settled("native-pay-receipt")
    doc = PaymentDocument.objects.get(payment=payment)
    owner = payment.member
    grant = _member_client(owner, space).get(
        f"/api/v1/member/makerspaces/{space.pk}/payment-documents/{doc.pk}/download-url")
    assert grant.status_code == 200, grant.data
    download = _member_client(owner).get(grant.data["url"])
    assert download.status_code == 200 and download["Content-Type"] == "application/pdf"
    other = make_payer("native-pay-receipt-other", space)
    assert _member_client(other).get(grant.data["url"]).status_code == 403


def test_native_staff_records_and_amends_a_manual_settlement_with_web_authority():
    space = make_space("native-pay-staff")
    payment = _dues(space, make_payer("native-pay-staff-payer", space))
    staff = _staff_client(space, "native-pay-staff-manager")
    url = f"/api/v1/admin/makerspace/{space.pk}/payments"
    ledger = staff.get(url)
    assert ledger.status_code == 200, ledger.data
    marked = staff.post(f"{url}/{payment.pk}/mark-offline",
                        settlement_payload(method="upi", reference="UPI-9"), format="json")
    assert marked.status_code == 200, marked.data
    amended = staff.post(f"{url}/{payment.pk}/amend-settlement",
                         settlement_payload(method="cash", reference="till-2"), format="json")
    assert amended.status_code == 200, amended.data
    rows = list(ManualSettlement.objects.filter(payment=payment).order_by("pk"))
    assert [row.method for row in rows] == ["upi", "cash"] and rows[1].amends_id == rows[0].pk
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_OFFLINE


def test_staff_payment_routes_refuse_member_grants_and_headerless_staff_grants():
    space = make_space("native-pay-staff-refused")
    payer = make_payer("native-pay-staff-refused-payer", space)
    payment = _dues(space, payer)
    url = f"/api/v1/admin/makerspace/{space.pk}/payments/{payment.pk}/mark-offline"
    body = settlement_payload(method="cash")
    assert _member_client(payer, space).post(url, body, format="json").status_code == 403
    headerless = _staff_client(space, "native-pay-staff-headerless", header=False)
    assert headerless.post(url, body, format="json").status_code == 403
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING and not ManualSettlement.objects.filter(payment=payment).exists()
