"""Own-charge routes preserve the member 403 contract and owner filtering (decision 494)."""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.payments.models import Payment, PaymentClaim, RefundCase
from apps.payments.services_refund_cases import request_refund
from tests.accounts.account_factories import make_membership
from tests.payments.ledger_fixtures_cx11b_g5 import seed, settled
from tests.payments.route_support_cx11b_g5 import cycle, hidden, ids, personal_client, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger]
OPS = ("member-paid-claim", "member-refund-request", "member-refund-withdraw", "member-payment-history", "member-archived-payments")
CASES = [(name, key, native) for name in OPS for key in (
    "payments", "charges.enabled", "membership", "charges.membership",
    *(("billing.offline_claims",) if name == "member-paid-claim" else ()))
    for native in (False, True)]


@pytest.mark.parametrize("name,key,native", CASES)
def test_member_money_route_exact_effect_no_other_owner_and_independent_switches(name, key, native):
    s = seed(native)
    make_membership(s.actor, s.space)
    other = personal_client(s.actor, s.space, native)
    kwargs, body, method, on, audit = {"makerspace_id": s.space.pk}, {}, "POST", (200, None), ()
    case = None
    if name == "member-paid-claim":
        kwargs["payment_id"] = s.payment.pk
        body = {"reference": "G5-CLAIM", "paid_on": timezone.localdate().isoformat()}
        on, audit = (201, None), ("payment.paid_claim_submitted",)
    elif name in {"member-refund-request", "member-refund-withdraw"}:
        settled(s)
        if name == "member-refund-request":
            kwargs["payment_id"] = s.payment.pk
            body, on, audit = {"reason": "G5 owner request"}, (201, None), ("payment.refund_case_opened",)
        else:
            case = request_refund(s.payment, member=s.payer, reason="G5 owner request")
            kwargs["case_id"], audit = case.pk, ("payment.refund_case_withdrawn",)
    else:
        method = "GET"
        if name == "member-archived-payments":
            s.space.archived_at = timezone.now()
            s.space.save(update_fields=["archived_at"])
            kwargs = {}
            if native:
                # Global recovery discovery intentionally has no selected live space.
                for caller in (s.payer_client, other, s.foreign):
                    caller._credentials.pop("HTTP_X_MAKERSPACE_ID", None)
    def result(response):
        saved = Payment.objects.get(pk=s.payment.pk)
        if name == "member-paid-claim":
            claim = PaymentClaim.objects.get(pk=response.data["id"])
            assert (claim.payment_id, claim.claimant_id, claim.reference, claim.status) == (saved.pk, s.payer.pk, "G5-CLAIM", "submitted")
            assert saved.status == "pending" and saved.manual_settlements.count() == 0
        elif name.startswith("member-refund-"):
            row = RefundCase.objects.get(pk=response.data["id"])
            expected = "open" if name.endswith("request") else "withdrawn"
            assert (row.payment_id, row.requested_by_id, row.member_reason, row.status) == (saved.pk, s.payer.pk, "G5 owner request", expected)
            assert saved.status == "paid_offline" and saved.refunds.count() == 0
        elif name == "member-payment-history":
            assert ids(response) == [saved.pk] and Decimal(response.data[0]["amount"]) == Decimal("100")
        else:
            assert response.data == [{"makerspace": {"id": s.space.pk, "name": s.space.name, "slug": s.space.slug},
                                      "pending_count": 1, "total_count": 1}]
    def empty(response):
        assert response.data == []
    if method == "GET":
        probes = [(other, (200, None), empty)]
        if name != "member-archived-payments":
            probes.append(hidden(s.foreign, (403, "permission_denied")))
        else:
            probes.append((s.foreign, (200, None), empty))
    else:
        probes = [hidden(other, (404, "not_found"))]
        # Refund members without membership/charges retain 403 (494); claim lookup is owner-scoped 404.
        probes.append(hidden(s.foreign, (404, "not_found") if name == "member-paid-claim" and not native else (403, "permission_denied")))
    w = world(s.space, s.payer_client, reverse(name, kwargs=kwargs), method, body, on, audit, result, probes)
    cycle(w, key, (404, "feature_disabled") if key == "billing.offline_claims" else None)
