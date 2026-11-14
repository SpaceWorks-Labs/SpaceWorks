"""Bearer pay links and public quotes prove concrete money/subject content and signed access."""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.makerspaces.models import MembershipPlan
from apps.payments import pay_links
from apps.payments.models import Payment, PaymentClaim, PaymentPayLink
from tests.l5_local.helpers import accountless
from tests.payments.ledger_fixtures_cx11b_g5 import seed
from tests.payments.route_support_cx11b_g5 import cycle, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,key", [("pay-link", "billing.pay_links"), ("pay-link", "payments"),
    ("pay-link-claim", "billing.pay_links"), ("pay-link-claim", "billing.offline_claims"), ("pay-link-claim", "payments")])
def test_pay_link_route_exact_subject_and_effect_signed_access_and_independent_switches(native, name, key):
    s = seed(native)
    payment = accountless(s.space, s.actor)
    link, token = pay_links.create_link(actor=s.actor, makerspace_id=s.space.pk, payment_id=payment.pk)
    method = "GET" if name == "pay-link" else "POST"
    body = {} if method == "GET" else {"reference": "G5-BEARER-CLAIM", "paid_on": timezone.localdate().isoformat()}
    bad_url = reverse(name, kwargs={"token": "forged-token"})
    def invalid(w):
        return s.foreign.get(bad_url) if method == "GET" else s.foreign.post(bad_url, body, format="json")
    def result(response):
        if method == "GET":
            assert {field: response.data[field] for field in ("label", "amount", "currency", "status", "instructions")} == {
                "label": "Workshop fee", "amount": "75.00", "currency": "inr", "status": "pending", "instructions": "G5 pay at desk"}
            assert PaymentPayLink.objects.get(pk=link.pk).last_used_at is not None
        else:
            claim = PaymentClaim.objects.get(pk=response.data["id"])
            assert (claim.payment_id, claim.pay_link_id, claim.claimant_id, claim.reference) == (payment.pk, link.pk, None, "G5-BEARER-CLAIM")
            assert Payment.objects.get(pk=payment.pk).status == "pending"
            assert payment.manual_settlements.count() == 0
    # Public bearer access, not membership: unknown/forged tokens keep pay_link_invalid (520).
    w = world(s.space, s.payer_client if native else APIClient(), reverse(name, kwargs={"token": token}), method, body,
        on=(200, None) if method == "GET" else (201, None),
        audit=("payment.pay_link_used",) if method == "GET" else ("payment.paid_claim_submitted",),
        check=result, probes=[(invalid, (404, "pay_link_invalid"), lambda r: None)])
    w.read_only = False  # This GET deliberately records last use and its first-use audit.
    off = (404, "pay_link_invalid") if key == "billing.pay_links" else (404, "feature_disabled")
    cycle(w, key, None if key == "payments" else off)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key,code", [("charges.pricing", "pricing_disabled"), ("charges.enabled", "charges_off"),
    ("charges.membership", "charges_off"), ("membership", "not_found"), ("member_accounts", "not_found")])
def test_public_pricing_quote_exact_seeded_plan_no_standing_and_each_dependency(native, key, code):
    s = seed(native)
    plan = MembershipPlan.objects.create(makerspace=s.space, name="G5 public plan", interval="monthly", amount="12.50", currency="inr", is_public=True)
    body = {"domain": "membership", "plan_id": plan.pk}
    url = reverse("pricing-quote", kwargs={"makerspace_slug": s.space.slug})
    def result(response):
        assert Decimal(response.data["quote"]["total"]) == Decimal("12.50")
        assert Decimal(response.data["tax"]["gross"]) == Decimal("12.50")
        assert response.data["quote"]["lines"][0]["target"] == {"type": "membership_plan", "id": plan.pk, "label": "G5 public plan"}
        assert response.data["digest"] == response.data["quote"]["digest"]
        assert Payment.objects.filter(makerspace=s.space).count() == 1
    off = (404, code)
    # 481/494 exclude this public anonymous surface: no tenant membership is needed to quote a public plan.
    probes = [(lambda w: APIClient().post(url, body, format="json"),
               lambda disabled: off if disabled else (200, None), lambda r: None)]
    cycle(world(s.space, s.payer_client if native else APIClient(), url, "POST", body, check=result, probes=probes), key, off)
