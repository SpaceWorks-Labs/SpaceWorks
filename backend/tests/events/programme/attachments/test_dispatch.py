"""Default-on source dispatch and provider failure semantics, without network."""
from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import Mock
import pytest
from apps.integrations import notification_attachment_sources as sources
from apps.integrations.notification_document_dispatch import send_document
from apps.integrations.notification_providers import ProviderResult


@pytest.fixture(autouse=True)
def source_boundaries_are_explicit_unit_fakes(monkeypatch):
    monkeypatch.setattr("apps.tenant_migration.gate_runtime.boundary_tenant_write", lambda tenant_id: nullcontext())


@pytest.fixture
def delivery():
    return SimpleNamespace(makerspace_id=9, envelope=SimpleNamespace(source_kind="events.certificate",
        source_id="81", recipient_id=18, makerspace_id=9, audience="requester", revision="2"))


@pytest.fixture
def source(monkeypatch):
    reference = sources.AttachmentReference("events.certificate", 81, "certificate", "2")
    authorize = Mock(return_value=object())
    render = Mock(return_value=("certificate.pdf", b"%PDF-1.7\nprivate-owner", "application/pdf"))
    provider = sources.AttachmentSource(lambda _: (reference,), authorize, render, "certificate")
    monkeypatch.setitem(sources._SOURCES, "events.certificate", provider)
    return provider


def provider(result=ProviderResult(True, "pdf-message")):
    return SimpleNamespace(send_document=Mock(return_value=result), send=Mock(return_value=ProviderResult(True, "text")))


def test_personal_certificate_pdf_is_default_without_an_attachment_switch(delivery, source):
    chat = provider()
    assert send_document(chat, delivery, {"text": "Ready"}).accepted
    chat.send_document.assert_called_once()
    chat.send.assert_not_called()
    assert chat.send_document.call_args.kwargs["pdf_bytes"].startswith(b"%PDF-")
    assert source.authorize.call_count >= 2
    assert all(call.kwargs == {"makerspace_id": 9, "recipient_id": 18} for call in source.authorize.call_args_list)


@pytest.mark.parametrize("result", [ProviderResult(False, error_code="unsupported"),
    ProviderResult(False, error_code="provider_error")])
def test_definitive_unsupported_attachment_falls_back_to_navigation(delivery, source, result):
    chat = provider(result)
    assert send_document(chat, delivery, {"text": "Sign in"}).accepted
    chat.send.assert_called_once()


@pytest.mark.parametrize("result", [ProviderResult(False, retryable=True, error_code="unavailable"),
    ProviderResult(False, retryable=True, ambiguous=True, error_code="timeout"),
    ProviderResult(False, ambiguous=True, error_code="timeout")])
def test_retryable_or_ambiguous_never_immediately_duplicates_text(delivery, source, result):
    chat = provider(result)
    assert send_document(chat, delivery, {"text": "Ready"}) == result
    chat.send.assert_not_called()


def test_oversize_is_shared_retryable_failure_without_text(delivery, source):
    source.render.return_value = ("certificate.pdf", b"%PDF-" + b"x" * (5 * 1024 * 1024), "application/pdf")
    chat = provider()
    result = send_document(chat, delivery, {})
    assert not result.accepted and result.retryable and result.error_code == "document_size_exceeded"
    chat.send_document.assert_not_called()
    chat.send.assert_not_called()


def test_room_or_wrong_source_revision_never_renders(delivery, source):
    chat = provider()
    delivery.envelope.audience = "staff"
    assert send_document(chat, delivery, {}).error_code == "document_not_authorized"
    source.render.assert_not_called()
    delivery.envelope.audience = "requester"
    delivery.envelope.revision = "3"
    assert send_document(chat, delivery, {}).error_code == "document_not_authorized"
    source.render.assert_not_called()


def test_owner_revocation_during_render_drops_bytes(delivery, source):
    def render(*args, **kwargs):
        source.authorize.side_effect = sources.DocumentDeliveryError("document_not_authorized")
        return "certificate.pdf", b"%PDF-1.7\nprivate-owner", "application/pdf"
    source.render.side_effect = render
    chat = provider()
    assert send_document(chat, delivery, {}).error_code == "document_not_authorized"
    chat.send_document.assert_not_called()


def test_revoked_certificate_notice_stays_navigation_only():
    from apps.integrations.notification_certificate_media import references
    assert references(SimpleNamespace(event="certificate_revoked")) == ()


def test_no_public_message_json_can_invent_an_attachment(delivery):
    delivery.envelope.source_kind = "unregistered"
    delivery.envelope.context = {"attachments": [{"certificate_id": 81}]}
    assert sources.attachment_references(delivery.envelope) == ()
