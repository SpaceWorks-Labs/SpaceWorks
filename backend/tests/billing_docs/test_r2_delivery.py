"""Document capabilities obey the existing claim, retry, and audience rules."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.notification_delivery import ensure_deliveries, send
from apps.integrations.notification_providers import PROVIDERS, ProviderResult
from apps.payments.notifications_p2 import notify_document

pytestmark = pytest.mark.django_db


class DocumentProvider:
    def __init__(self, results):
        self.results = iter(results)
        self.documents = []
        self.texts = []

    def send_document(self, delivery, *, filename, pdf_bytes, caption):
        self.documents.append((delivery.pk, filename, pdf_bytes, caption))
        return next(self.results)

    def send(self, delivery, rendered):
        self.texts.append((delivery.pk, rendered))
        return ProviderResult(True, "text-message-id")


@pytest.fixture
def document_delivery(lane, document, document_mail):
    envelope = NotificationEnvelope.objects.get(source_kind="payments.document", source_id=str(document.pk))
    ensure_deliveries(envelope)
    return envelope.deliveries.get(channel="telegram")


def provider(monkeypatch, results):
    fake = DocumentProvider(results)
    monkeypatch.setitem(PROVIDERS, ("telegram", "telegram"), lambda _: fake)
    return fake


def test_successful_document_send_cannot_also_send_text_or_duplicate(document_delivery, monkeypatch):
    fake = provider(monkeypatch, [ProviderResult(True, "document-message-id")])
    send(document_delivery.pk)
    send(document_delivery.pk)
    document_delivery.refresh_from_db()
    assert document_delivery.state == "accepted" and document_delivery.attempt_count == 1
    assert len(fake.documents) == 1 and fake.texts == []
    assert fake.documents[0][1].endswith(".pdf") and fake.documents[0][2].startswith(b"%PDF-")


@pytest.mark.parametrize("result", [
    ProviderResult(False, error_code="unsupported_document"),
    ProviderResult(False, error_code="provider_error"),
    ProviderResult(False, error_code="invalid_endpoint"),
])
def test_definite_permanent_failure_falls_back_to_one_text_notice(document_delivery, monkeypatch, result):
    fake = provider(monkeypatch, [result])
    send(document_delivery.pk)
    send(document_delivery.pk)
    document_delivery.refresh_from_db()
    assert document_delivery.state == "accepted"
    assert len(fake.documents) == len(fake.texts) == 1
    assert "token=" not in fake.texts[0][1]["text"]


@pytest.mark.parametrize("result", [
    ProviderResult(False, error_code="unavailable", retryable=True),
    ProviderResult(False, error_code="rate_limited", retryable=True, retry_after=120),
    ProviderResult(False, error_code="timeout", retryable=True, ambiguous=True),
])
def test_transient_or_ambiguous_document_failure_never_sends_text(document_delivery, monkeypatch, result):
    fake = provider(monkeypatch, [result])
    send(document_delivery.pk)
    document_delivery.refresh_from_db()
    assert document_delivery.state == "retrying" and document_delivery.retryable
    assert document_delivery.next_attempt_at > timezone.now()
    assert len(fake.documents) == 1 and fake.texts == []


def test_retry_rerenders_document_from_live_reference(document_delivery, document_mail, monkeypatch):
    fake = provider(monkeypatch, [ProviderResult(False, error_code="unavailable", retryable=True),
                                 ProviderResult(True, "retry-document-id")])
    send(document_delivery.pk)
    NotificationDelivery.objects.filter(pk=document_delivery.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    send(document_delivery.pk)
    assert len(fake.documents) == 2 and fake.texts == []
    assert fake.documents[0][2] != fake.documents[1][2]
    assert document_mail.rendered == [int(document_delivery.envelope.source_id)] * 2


def test_unsupported_provider_capability_sends_text_once(document_delivery, lane):
    # Existing adapters that do not expose the optional capability still work.
    send(document_delivery.pk)
    send(document_delivery.pk)
    assert len(lane.fake.calls) == 1


def test_oversize_chat_document_is_retryable_and_never_text_only(document_delivery, monkeypatch):
    fake = provider(monkeypatch, [])
    monkeypatch.setattr("apps.payments.document_pdf.render_document_pdf", lambda row: b"x" * (5 * 1024 * 1024 + 1))
    send(document_delivery.pk)
    document_delivery.refresh_from_db()
    assert document_delivery.state == "retrying" and document_delivery.retryable
    assert not fake.documents and not fake.texts


def test_documents_never_fan_out_to_staff_or_makerspace_rooms(document, lane, monkeypatch):
    dispatch = Mock(side_effect=AssertionError("Private document reached a group channel"))
    monkeypatch.setattr("apps.integrations.dispatch_channels.dispatch_channel", dispatch)
    notify_document(document)
    assert not dispatch.called
    envelopes = NotificationEnvelope.objects.filter(source_kind="payments.document", source_id=str(document.pk))
    assert list(envelopes.values_list("recipient_id", "audience")) == [(document.payment.member_id, "requester")]


def test_unknown_document_kind_stays_text_only(monkeypatch):
    from apps.payments.document_delivery import attachment_references
    monkeypatch.setattr("apps.payments.notifications_p2.document_eligible", lambda envelope: True)
    query = Mock()
    query.get.return_value = SimpleNamespace(pk=1, kind="future_kind")
    monkeypatch.setattr("apps.operations.notifications_p2.scoped", lambda *args, **kwargs: query)
    assert attachment_references(SimpleNamespace(source_kind="payments.document", makerspace_id=1, source_id="1")) == ()


def test_unknown_kind_compatibility_mail_remains_text_only(monkeypatch):
    from apps.integrations.delivery_content import content
    from apps.payments.document_delivery import prepare_document_email
    document = SimpleNamespace(kind="future_kind", payment=SimpleNamespace(member=SimpleNamespace(email="payer@example.test")))
    monkeypatch.setattr("apps.payments.document_delivery.authorized_document", lambda *args, **kwargs: document)
    monkeypatch.setattr("apps.payments.notifications_p2.document_body", lambda row: {"subject": "Future document", "text": "Available"})
    log = SimpleNamespace(source_metadata={"document": {"document_id": 1, "kind": "future_kind"}},
                          source_id="1", event="document_issued", makerspace_id=1, recipient_id=1)
    assert prepare_document_email(log)
    assert content(log).attachments == () and content(log).to_email == "payer@example.test"


def test_media_cleanup_failure_does_not_block_unrelated_outbox_work(document_delivery, monkeypatch):
    from apps.integrations.notification_tasks import sweep_notification_outbox
    cleanup = Mock(side_effect=RuntimeError("unavailable"))
    enqueue = Mock()
    monkeypatch.setattr("apps.integrations.notification_media.cleanup_grants", cleanup)
    monkeypatch.setattr("apps.integrations.notification_tasks.deliver_envelope.delay", enqueue)
    sweep_notification_outbox()
    assert document_delivery.envelope_id in [call.args[0] for call in enqueue.call_args_list]
