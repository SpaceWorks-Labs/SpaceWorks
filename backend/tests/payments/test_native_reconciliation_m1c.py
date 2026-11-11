"""Phase 1c: staff reconciliation closes Orders locally and still cancels Links."""

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.audit.models import AuditLog
from apps.payments.models import ManualSettlement, Payment
from apps.payments.providers.razorpay import RazorpayProvider
from apps.payments.reconciliation import reconcile_payments
from tests.payments.test_mobile_intent_vendor import _razorpay_debt
from tests.return_helpers import make_member, settlement_details

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("target_status", [Payment.Status.WAIVED, Payment.Status.PAID_OFFLINE])
@pytest.mark.parametrize("native", [True, False])
def test_reconciliation_persists_closure_without_canceling_native_orders(monkeypatch, target_status, native):
    space, member, payment = _razorpay_debt("m1c-reconcile", claimed=True)
    staff = make_member("m1c-reconcile-staff", space)
    payment.online_rail = (
        Payment.OnlineRail.NATIVE_PAYMENT_INTENT if native else Payment.OnlineRail.CHECKOUT
    )
    payment.external_order_id = "order_m1c_close" if native else "plink_m1c_close"
    payment.save()
    calls = []

    def request(self, source, method, path, body=None):
        calls.append((method, path))
        return {}

    monkeypatch.setattr(RazorpayProvider, "_request", request)
    # Owning the debt grants no authority to settle or waive it.
    before = Payment.objects.filter(pk=payment.pk).values().get()
    with pytest.raises(PermissionDenied):
        reconcile_payments(
            actor=member, makerspace_id=space.pk, payment_ids=[payment.pk],
            target_status=target_status,
            settlement=settlement_details() if target_status == Payment.Status.PAID_OFFLINE else None,
        )
    assert Payment.objects.filter(pk=payment.pk).values().get() == before
    assert not ManualSettlement.objects.filter(payment=payment).exists()
    assert calls == []

    reconcile_payments(
        actor=staff, makerspace_id=space.pk, payment_ids=[payment.pk],
        target_status=target_status,
        settlement=settlement_details() if target_status == Payment.Status.PAID_OFFLINE else None,
    )

    payment.refresh_from_db()
    assert payment.status == target_status
    assert payment.stripe_checkout_session_expired_at is not None
    assert payment.external_order_id == ("order_m1c_close" if native else "plink_m1c_close")
    assert calls == ([] if native else [("POST", "/payment_links/plink_m1c_close/cancel")])
    assert ManualSettlement.objects.filter(payment=payment).count() == (
        target_status == Payment.Status.PAID_OFFLINE
    )
    if target_status == Payment.Status.PAID_OFFLINE:
        assert ManualSettlement.objects.get(payment=payment).recorded_by_id == staff.pk
    action = "payment.paid_offline" if target_status == Payment.Status.PAID_OFFLINE else "payment.waived"
    assert AuditLog.objects.filter(
        makerspace=space, target_type="payments.payment", target_id=str(payment.pk), action=action,
    ).count() == 1
