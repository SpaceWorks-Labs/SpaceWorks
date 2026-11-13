"""Real account-only payer, ledger, and personal endpoint fixtures."""
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.integrations.models import NotificationPreference as Matrix
from apps.integrations.models_contract import NotificationEnvelope
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.models import PaymentDocument
from apps.payments.reconciliation import mark_offline
from tests.p2_n_other.conftest import lane, payment  # noqa: F401
from tests.return_helpers import settlement_details


@pytest.fixture
def document(request, lane, payment):
    kind = getattr(request, "param", "receipt")
    if kind == "bill":
        # Lane r1 supplies this service; kinds stay plain strings in lane r2.
        from apps.payments.documents import issue_bill
        return issue_bill(payment, actor=lane.manager)
    mark_offline(payment, lane.manager, settlement=settlement_details())
    payment.refresh_from_db()
    if kind == "credit_note":
        from apps.payments.services_refunds_offline import record_offline_refund
        refund = record_offline_refund(payment, amount="5.00", reason="Return", actor=lane.manager,
            receipt={"method": "cash", "reference": "desk", "refunded_at": timezone.now()})
        return PaymentDocument.objects.get(refund=refund)
    return PaymentDocument.objects.get(payment=payment, kind="receipt", reverses__isnull=True)


@pytest.fixture
def document_mail(lane, document, monkeypatch, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    # Tenant mail needs the opt-in `email` module (dispatch.email_module_blocks), off for a new space.
    lane.space.enabled_modules = sorted(set(lane.space.enabled_modules or []) | {"email"})
    lane.space.save(update_fields=["enabled_modules"])
    monkeypatch.setattr("apps.integrations.email.makerspace_mail_connection", lambda space: (None, "billing@example.test"))
    monkeypatch.setattr("apps.integrations.timing_dispatch.defer_log", lambda *args, **kwargs: False)
    rendered = []

    def pdf(row):
        rendered.append(row.pk)
        return b"%PDF-1.7\nprivate-payer-document-" + str(len(rendered)).encode()

    monkeypatch.setattr("apps.payments.document_pdf.render_document_pdf", pdf)

    def route(path):
        Matrix.objects.update_or_create(makerspace=lane.space, feature="payments", channel="email",
                                        defaults={"enabled": path == "envelope"})
        NotificationPreference.objects.filter(makerspace=lane.space, user=document.payment.member,
            category="payments").update(channels=["email"] if path == "envelope" else ["telegram"])
        return NotificationEnvelope.objects.get(source_kind="payments.document", source_id=str(document.pk))

    return SimpleNamespace(rendered=rendered, route=route)
