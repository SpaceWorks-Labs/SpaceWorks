"""Every remaining gift/pledge link and owner route has exact money/content proof."""
from decimal import Decimal
from io import BytesIO

import pytest
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader

from apps.payments.donations.identity import PLEDGE_SALT, STATUS_SALT, link_token
from apps.payments.donations.models import Donation, DonationPledge, DonationSettings
from apps.payments.donations.tax_receipts import freeze
from apps.payments.models import Payment, PaymentClaim
from tests.accounts.account_factories import make_membership
from tests.payments.ledger_fixtures_cx11b_g5 import seed
from tests.payments.route_support_cx11b_g5 import cycle, hidden, ids, personal_client, world
from tests.payments_rail.ports_cx11b_g5 import configure

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger]
OPS = (
    ("public-donation-status", "GET", ("finance.donations",)),
    ("public-donation-checkout", "POST", ("finance.donations", "payments", "payments.enabled", "payments.donations")),
    ("public-donation-claim", "POST", ("finance.donations", "billing.offline_claims")),
    ("public-donation-tax-receipt", "GET", ("finance.donations", "finance.tax_exempt_receipts")),
    ("public-pledge-manage", "GET", ("finance.donations", "finance.recurring_donations")),
    ("public-pledge-manage", "POST", ("finance.donations", "finance.recurring_donations")),
    ("member-donations", "GET", ("finance.donations",)),
    ("member-donation-tax-receipt", "GET", ("finance.donations", "finance.tax_exempt_receipts")),
    ("member-pledges", "GET", ("finance.donations", "finance.recurring_donations")),
    ("member-pledge", "POST", ("finance.donations", "finance.recurring_donations")),
)
CASES = [(name, method, key, native) for name, method, keys in OPS
         for key in (*keys, "charges.enabled", "charges.donations") for native in (False, True)]


@pytest.mark.parametrize("name,method,key,native", CASES)
def test_donation_route_exact_effect_signed_or_owner_standing_and_restore(name, method, key, native, monkeypatch):
    s = seed(native)
    member, pledge_route, tax = name.startswith("member-"), "pledge" in name, "tax-receipt" in name
    donor = s.payer if member else None
    gift = Donation.objects.create(makerspace=s.space, donor=donor, donor_name="G5 retained giver",
        donor_email="giver@example.test", amount="10.00", currency="inr", created_by=s.actor,
        wants_tax_receipt=tax, status="paid" if tax else "pending", paid_at=timezone.now() if tax else None)
    payment = Payment.objects.create(makerspace=s.space, subject_type="donation", subject_id=gift.pk, member=donor,
        amount="10.00", currency="inr", created_by=s.actor, provider="unclaimed")
    pledge = DonationPledge.objects.create(makerspace=s.space, donor=donor, donor_name="G5 retained giver",
        amount="10.00", currency="inr", starts_on=timezone.localdate(), next_due_on=timezone.localdate(), created_by=s.actor)
    if tax:
        DonationSettings.objects.create(makerspace=s.space, is_nonprofit=True, legal_name="G5 Charity",
            tax_exemptions=[{"scheme": "us_501c3", "number": "G5-CHARITY", "valid_from": "", "valid_until": ""}])
        assert freeze(gift)["amount"] == "10.00"
    body, audit, on = {}, (), (200, None)
    if pledge_route and method == "POST":
        body, audit = {"action": "pause"}, ("pledge.paused",)
    elif name == "public-donation-claim":
        body = {"reference": "G5-GIFT-CLAIM", "paid_on": timezone.localdate().isoformat()}
        audit, on = ("payment.paid_claim_submitted",), (201, None)
    elif name == "public-donation-checkout":
        s.space.enabled_features += ["payments.donations"]
        s.space.save(update_fields=["enabled_features"])
        configure(s, monkeypatch)
        audit = ("payment.checkout_created",)
    if member:
        kwargs = {"makerspace_id": s.space.pk}
        if name in {"member-pledge", "member-donation-tax-receipt"}:
            kwargs["pk"] = pledge.pk if pledge_route else gift.pk
    else:
        token = link_token(pledge, "manage_secret", PLEDGE_SALT) if pledge_route else link_token(gift, "access_secret", STATUS_SALT)
        kwargs = {"token": token}
    url = reverse(name, kwargs=kwargs)
    if key in {"payments", "payments.enabled", "payments.donations"}:
        off = (503, "payments_unavailable")
    elif not member and (key == "finance.donations" or pledge_route):
        off = (404, "donation_link_invalid")
    else:
        off = (404, "feature_disabled")

    def result(response):
        if tax:
            assert response["Content-Type"] == "application/pdf" and response["Cache-Control"] == "private, no-store"
            text = " ".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
            assert "G5 retained giver" in text and "G5-CHARITY" in text and gift.tax_receipt["number"] in text
        elif name in {"member-donations", "member-pledges"}:
            expected = pledge.pk if pledge_route else gift.pk
            assert ids(response) == [expected] and Decimal(response.data[0]["amount"]) == Decimal("10")
        elif pledge_route:
            saved = DonationPledge.objects.get(pk=pledge.pk)
            assert (response.data["id"], saved.status) == (pledge.pk, "paused" if method == "POST" else "active")
            assert saved.amount == Decimal("10") and Payment.objects.filter(subject_type="donation", subject_id=gift.pk).count() == 1
        elif name == "public-donation-claim":
            row = PaymentClaim.objects.get(pk=response.data["id"])
            assert (row.payment_id, row.claimant_id, row.reference) == (payment.pk, None, "G5-GIFT-CLAIM")
            assert Payment.objects.get(pk=payment.pk).status == "pending"
        else:
            assert (response.data["id"], Decimal(response.data["amount"]), response.data["currency"]) == (gift.pk, Decimal("10"), "inr")
            if name == "public-donation-checkout":
                saved = Payment.objects.get(pk=payment.pk)
                assert (saved.provider, saved.external_order_id, saved.online_rail) == ("stripe", "cs_g5", "checkout")
                assert response.data["checkout_url"] == "https://checkout.example.test/g5"
    if member:
        make_membership(s.actor, s.space)
        other = personal_client(s.actor, s.space, native)
        if name in {"member-pledges", "member-donations"}:
            def own_empty(response):
                if response.status_code == 200:
                    assert response.data == []
            probes = [(other, lambda disabled: off if disabled and not key.startswith("charges.") else (200, None), own_empty)]
        else:
            # 520 resolves private ownership before gate disclosure. The tax surface's existing
            # no_tax_receipt shape conceals a non-owned row just like an absent receipt.
            probes = [hidden(other, (404, "no_tax_receipt") if tax else (404, "not_found"))]
    else:
        # 520: the actual bearer contract keeps authentication/signature failure unchanged.
        bad = reverse(name, kwargs={"token": "forged"})
        def invalid(w):
            return s.foreign.get(bad) if method == "GET" else s.foreign.post(bad, body, format="json")
        probes = [(invalid, (404, "donation_link_invalid"), lambda r: None)]
    cycle(world(s.space, s.payer_client, url, method, body, on, audit, result, probes), key,
          None if key.startswith("charges.") else off)
