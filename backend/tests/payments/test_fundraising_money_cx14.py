"""Ledger-first gifts and sponsorship: no real card calls, one charge and receipt."""

from decimal import Decimal
from unittest.mock import Mock

import pytest

from apps.audit.models import AuditLog
from apps.payments import checkout_coordination
from apps.payments.donations.identity import Donor
from apps.payments.donations.models import Donation, Sponsor, SponsorshipCharge
from apps.payments.donations.services import checkout_url, create_gift
from apps.payments.donations.sponsors import raise_charge
from apps.payments.models import ManualSettlement, Payment
from apps.payments.resolution import PaymentSource
from tests.l18_local.helpers import client, setup, staff, switch
from tests.money_modes.helpers import OFFLINE, ONLINE, fake_provider, set_mode
from tests.return_helpers import settlement_payload

pytestmark = pytest.mark.django_db


def raise_money(space, actor, account, kind):
    if kind == "donation":
        donor = Donor(account=account, actor=account, name="Giver", email=account.email)
        return create_gift(space, donor, amount=Decimal("25.00"))
    sponsor = Sponsor.objects.create(makerspace=space, name="Supporter", created_by=actor)
    return raise_charge(sponsor, actor=actor, amount=Decimal("25.00"))


@pytest.mark.parametrize("kind", ["donation", "sponsorship"])
@pytest.mark.parametrize("mode", [OFFLINE, ONLINE])
def test_both_money_sources_record_one_charge_before_optional_rail(kind, mode, monkeypatch):
    space, _manager, account = setup("cx14-money", "finance.sponsors")
    set_mode(space, "donations", mode)
    actor = staff("cx14-money", space, "fundraising")
    checkout = Mock()
    monkeypatch.setattr("apps.payments.services_checkout.stripe_client.create_checkout_session", checkout)
    claim = Mock(wraps=checkout_coordination._claim_provider)
    monkeypatch.setattr(checkout_coordination, "_claim_provider", claim)
    # No configured credentials: recording the debt does not reach a provider.
    subject, payment = raise_money(space, actor, account, kind)
    assert Payment.objects.filter(makerspace=space, subject_type=kind, subject_id=subject.pk).count() == 1
    assert payment.amount == Decimal("25.00")
    assert payment.status == Payment.Status.PENDING
    assert payment.provider == Payment.Provider.UNCLAIMED
    action = "donation.created" if kind == "donation" else "sponsor.charge_raised"
    assert AuditLog.objects.filter(makerspace=space, action=action, meta__payment_id=payment.pk).count() == 1

    # Resolve a test source only now. Keep real checkout coordination and claiming;
    # the external Stripe call is the only checkout operation replaced by a stub.
    source = PaymentSource("raw", "sk_test_cx14", "whsec_test_cx14")
    monkeypatch.setattr("apps.payments.availability.resolve_payment_source", lambda _space: source)
    monkeypatch.setattr(checkout_coordination, "resolve_payment_source", lambda _space: source)
    monkeypatch.setattr(checkout_coordination, "source_for_payment", lambda _payment: source)
    monkeypatch.setattr("apps.payments.services_checkout.member_payment_return_url",
                        lambda _space: "https://members.test/payments")

    def provider_checkout(resolved_source, **params):
        assert resolved_source is source
        assert params["metadata"] == {"payment_id": str(payment.pk), "makerspace_id": str(space.pk)}
        assert Payment.objects.get(pk=payment.pk).provider == Payment.Provider.STRIPE
        return {"id": "cs_test_cx14", "url": "https://checkout.test/session"}

    checkout.side_effect = provider_checkout
    checkout.assert_not_called()
    claim.assert_not_called()
    assert checkout_url(payment) == ("" if mode == OFFLINE else "https://checkout.test/session")
    payment.refresh_from_db()
    assert payment.provider == (Payment.Provider.UNCLAIMED if mode == OFFLINE else Payment.Provider.STRIPE)
    assert payment.checkout_url == ("" if mode == OFFLINE else "https://checkout.test/session")
    assert payment.external_order_id == (None if mode == OFFLINE else "cs_test_cx14")
    assert payment.status == Payment.Status.PENDING
    # Reopening a live checkout neither reclaims the provider nor creates another page.
    assert checkout_url(payment) == ("" if mode == OFFLINE else "https://checkout.test/session")
    assert claim.call_count == (0 if mode == OFFLINE else 1)
    assert checkout.call_count == (0 if mode == OFFLINE else 1)
    assert Payment.objects.filter(makerspace=space, subject_type=kind, subject_id=subject.pk).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action=action, meta__payment_id=payment.pk).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="payment.checkout_created",
                                   target_id=str(payment.pk)).count() == (0 if mode == OFFLINE else 1)


@pytest.mark.parametrize("kind", ["donation", "sponsorship"])
def test_fundraising_settles_only_its_money_with_exactly_one_receipt(kind, django_capture_on_commit_callbacks):
    space, _manager, account = setup("cx14-offline", "finance.sponsors")
    set_mode(space, "donations", OFFLINE)
    switch(space, "billing.maker_checker", on=False)
    actor = staff("cx14-offline", space, "fundraising")
    subject, payment = raise_money(space, actor, account, kind)
    url = f"/api/v1/admin/makerspace/{space.pk}/payments/{payment.pk}/mark-offline"
    with django_capture_on_commit_callbacks(execute=True):
        response = client(actor).post(url, settlement_payload(reference="CX14-RECEIPT"), format="json")
    assert response.status_code == 200, response.content
    payment.refresh_from_db()
    assert (payment.status, payment.provider, payment.amount) == ("paid_offline", "unclaimed", Decimal("25.00"))
    receipt = ManualSettlement.objects.get(payment=payment)
    assert (receipt.method, receipt.reference, receipt.amount, receipt.currency, receipt.recorded_by_id) == (
        "cash", "CX14-RECEIPT", Decimal("25.00"), payment.currency, actor.pk)
    assert AuditLog.objects.filter(makerspace=space, action="payment.paid_offline", target_id=str(payment.pk)).count() == 1
    if kind == "donation":
        subject.refresh_from_db()
        assert subject.status == Donation.Status.PAID


@pytest.mark.parametrize("key", ["charges.enabled", "charges.donations"])
@pytest.mark.parametrize("kind", ["donation", "sponsorship"])
def test_charges_off_keeps_campaigns_free_and_refuses_real_money_without_rows(key, kind):
    from apps.payments.donations.gates import DonationRefused

    space, _manager, account = setup("cx14-charges", "finance.sponsors")
    actor = staff("cx14-charges", space, "fundraising")
    switch(space, key, on=False)
    response = client(actor).post(f"/api/v1/admin/makerspace/{space.pk}/donations/campaigns",
                                 {"name": "Free campaign", "slug": "free"}, format="json")
    assert response.status_code == 201, response.content
    before = AuditLog.objects.filter(makerspace=space).count()
    with pytest.raises(DonationRefused) as refused:
        raise_money(space, actor, account, kind)
    assert refused.value.status_code == 400
    assert refused.value.detail["code"] == "charges_off"
    assert Donation.objects.filter(makerspace=space).count() == 0
    assert SponsorshipCharge.objects.filter(makerspace=space).count() == 0
    assert Payment.objects.filter(makerspace=space).count() == 0
    assert AuditLog.objects.filter(makerspace=space).count() == before


def test_provider_failure_keeps_recorded_gift_and_debt(monkeypatch):
    space, _manager, account = setup("cx14-provider")
    set_mode(space, "donations", ONLINE)
    actor = staff("cx14-provider", space, "fundraising")
    checkout = fake_provider(monkeypatch)
    subject, payment = raise_money(space, actor, account, "donation")

    def fail(payment_id):
        assert Payment.objects.get(pk=payment_id).subject_id == subject.pk
        raise RuntimeError("Provider unavailable")

    checkout.side_effect = fail
    assert checkout_url(payment) == ""
    assert Donation.objects.get(pk=subject.pk).status == "pending"
    assert Payment.objects.get(pk=payment.pk).status == "pending"
    assert AuditLog.objects.filter(makerspace=space, action="donation.created").count() == 1


def test_fundraising_cannot_settle_membership_money():
    from apps.makerspaces.models import MakerspaceMembership
    from apps.payments.services import create_payment
    from tests.return_helpers import make_member

    space, _manager, _donor = setup("cx14-other-money")
    account = make_member("cx14-other-payer", space, membership_role="member")
    set_mode(space, "donations", OFFLINE)
    actor = staff("cx14-other-money", space, "fundraising")
    membership = MakerspaceMembership.objects.get(makerspace=space, user=account)
    # The subject is a real local membership; lack of subject authority must refuse it.
    payment = create_payment(makerspace=space, subject_type="makerspace_membership", subject_id=membership.pk,
                             member=account, amount=Decimal("25.00"), currency="inr", created_by=actor)
    before = AuditLog.objects.filter(makerspace=space).count()
    response = client(actor).post(
        f"/api/v1/admin/makerspace/{space.pk}/payments/{payment.pk}/mark-offline",
        settlement_payload(reference="FORBIDDEN"), format="json")
    assert response.status_code == 403, response.content
    assert response.json()["code"] == "permission_denied"
    payment.refresh_from_db()
    assert payment.status == "pending"
    assert not ManualSettlement.objects.filter(payment=payment).exists()
    assert AuditLog.objects.filter(makerspace=space).count() == before
