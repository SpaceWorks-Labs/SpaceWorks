"""Rail removal leaves offline bills, receipts, grants and refunds available."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.platform import module_enabled
from apps.payments.availability import online_payments_enabled_for
from apps.payments.documents import issue_bill
from apps.payments.models import PaymentDocument
from apps.payments.reconciliation import mark_offline
from apps.payments.services_refunds_offline import record_offline_refund
from apps.separability import registry
from tests.payments.recon_f_helpers import pending_charge
from tests.return_helpers import authenticated_client, make_user, settlement_details

pytestmark = pytest.mark.django_db


def test_offline_documents_and_private_download_survive_rail_tombstone(monkeypatch):
    space, staff, payment = pending_charge("recon-no-rail", provider="unclaimed")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"payments"})
    space.save(update_fields=["enabled_modules"])
    original = registry.runtime_active
    monkeypatch.setattr(registry, "runtime_active", lambda label: label != "payments_rail" and original(label))
    assert registry.runtime_active("payments") and not module_enabled(space, "payments")
    assert not online_payments_enabled_for(payment)
    def no_provider(*args, **kwargs):
        pytest.fail("Offline documents must not resolve or call a payment provider")
    monkeypatch.setattr("apps.payments.reconciliation_rail.source_for_payment", no_provider)
    monkeypatch.setattr("apps.payments.services_refunds.get_provider", no_provider)
    bill = issue_bill(payment, actor=staff)
    mark_offline(payment, staff, settlement_details(reference="desk-cash"))
    payment.refresh_from_db()
    assert payment.status == "paid_offline" and payment.provider == "unclaimed"
    receipt = PaymentDocument.objects.get(payment=payment, kind="receipt")
    assert bill.number == "BILL-000001" and receipt.number == "000001"
    assert receipt.settlement_reference == "desk-cash"
    assert receipt.settlement_method == "cash"
    assert receipt.issuer["name"] == space.name

    owner = authenticated_client(payment.member)
    grant = owner.get(reverse("member-payment-document-url", args=[space.pk, receipt.pk]))
    assert grant.status_code == 200 and grant.data["expires_in"] == 300
    response = owner.get(grant.data["url"])
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf" and response.content.startswith(b"%PDF-")
    stranger = authenticated_client(make_user("recon-no-rail-stranger"))
    assert stranger.get(grant.data["url"]).status_code == 403
    refund = record_offline_refund(payment, amount="2.00", reason="Tool returned", actor=staff,
        receipt={"method": "cash", "reference": "cash-back", "refunded_at": timezone.now()})
    assert PaymentDocument.objects.get(refund=refund).kind == "credit_note"
    assert PaymentDocument.objects.filter(payment=payment).count() == 3
