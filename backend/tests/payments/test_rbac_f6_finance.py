"""Finance and cash-recording authority is tenant-scoped and survives the payments module."""
import pytest
from django.utils import timezone

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.payments.models import ManualSettlement, Refund
from tests.module_helpers import disable_module
from tests.rbac_f6_helpers import charge, community_member, custom_actor
from tests.return_helpers import authenticated_client, make_member, make_space, settlement_payload

pytestmark = pytest.mark.django_db


def finance_route(case, space):
    member = community_member(space)
    payment = charge(space, member, status="paid_offline" if case in {"amend", "refund"} else "pending")
    base = f"/api/v1/admin/makerspace/{space.pk}"
    if case in {"amend", "refund"}:
        ManualSettlement.objects.create(
            payment=payment, amount=payment.amount, currency=payment.currency,
            method="cash", received_at=timezone.now(), recorded_by=member.user,
        )
    routes = {
        "list": ("get", f"{base}/payments", None),
        "counter": ("get", f"{base}/payments?for_recording=true", None),
        "report": ("get", f"{base}/analytics/payment-reconciliation", None),
        "export": ("get", f"{base}/reports/payment-reconciliation/export?format=csv", None),
        "mark": ("post", f"{base}/payments/{payment.pk}/mark-offline", settlement_payload()),
        "bulk": ("post", f"{base}/payments/bulk/mark-offline", {"ids": [payment.pk], **settlement_payload()}),
        "amend": ("post", f"{base}/payments/{payment.pk}/amend-settlement", settlement_payload(reference="corrected")),
        "refund": ("post", f"{base}/payments/{payment.pk}/refund-offline", {
            "amount": "2.00", "reason": "Returned cash", "receipt": {
                "method": "cash", "reference": "refund-1", "refunded_at": timezone.now().isoformat(),
            },
        }),
    }
    return payment, routes[case]


@pytest.mark.parametrize("case", ["list", "counter", "report", "export", "mark", "bulk", "amend", "refund"])
@pytest.mark.parametrize("authority", ["narrow", "missing", "foreign", "inventory"])
def test_finance_endpoint_matrix(case, authority):
    space = make_space("f6-finance-matrix")
    payment, (method, path, body) = finance_route(case, space)
    action = rbac.Action.VIEW_FINANCE if case in {"list", "report", "export"} else rbac.Action.RECORD_PAYMENT
    if authority == "inventory":
        actor = make_member("f6-money-inventory", space, membership_role="inventory_manager", role="requester")
    else:
        actor_space = make_space("f6-finance-other") if authority == "foreign" else space
        actor = custom_actor(actor_space, [] if authority == "missing" else [action])
    response = getattr(authenticated_client(actor), method)(path, body, format="json")
    if authority == "narrow":
        assert response.status_code == 200
        if method == "post":
            assert AuditLog.objects.filter(actor=actor, makerspace=space, target_id=str(payment.pk)).exists()
            if case in {"mark", "bulk"}:
                assert ManualSettlement.objects.filter(payment=payment, recorded_by=actor).exists()
            if case == "amend":
                assert ManualSettlement.objects.filter(payment=payment).count() == 2
            if case == "refund":
                assert Refund.objects.filter(payment=payment, created_by=actor, provider="manual").exists()
    else:
        assert response.status_code in (403, 404)
        assert not AuditLog.objects.filter(actor=actor, makerspace=space).exists()


def test_cash_work_and_finance_reads_survive_payments_module_off():
    space = make_space("f6-money-off")
    actor = custom_actor(space, [rbac.Action.VIEW_FINANCE, rbac.Action.RECORD_PAYMENT])
    payment = charge(space, community_member(space))
    disable_module(space, "payments")
    client = authenticated_client(actor)
    base = f"/api/v1/admin/makerspace/{space.pk}"
    assert client.get(f"{base}/payments").status_code == 200
    assert client.get(f"{base}/analytics/payment-reconciliation").status_code == 200
    assert client.post(f"{base}/payments/{payment.pk}/mark-offline", settlement_payload(), format="json").status_code == 200
