"""X4 (#27): chat PDFs need no switch -- on for every space, new or existing."""
from types import SimpleNamespace

import pytest

from apps.integrations import notification_attachment_sources as sources
from apps.integrations.notification_document_dispatch import send_document
from apps.integrations.notification_providers import ProviderResult
from apps.makerspaces.capability_definitions import FEATURES
from apps.makerspaces.module_registry import MODULE_KEYS


def test_no_module_or_capability_can_switch_chat_pdfs_off():
    keys = set(FEATURES) | set(MODULE_KEYS)
    assert not [key for key in keys if "pdf" in key and ("chat" in key or "document" in key and "billing" not in key)]


def test_a_registered_document_is_attached_without_any_flag(monkeypatch):
    reference = SimpleNamespace(source_kind="test.pdf", document_id="1", revision="1")
    monkeypatch.setattr(sources, "_SOURCES", {"test.pdf": SimpleNamespace()})
    monkeypatch.setattr("apps.integrations.notification_document_dispatch.attachment_references",
                        lambda envelope: (reference,))
    monkeypatch.setattr("apps.integrations.notification_document_dispatch.attachment_source_boundary",
                        lambda *args, **kwargs: __import__("contextlib").nullcontext())
    monkeypatch.setattr("apps.integrations.notification_document_dispatch.render_attachment",
                        lambda *args, **kwargs: ("receipt.pdf", b"%PDF-1.7", None))
    calls = []

    class Provider:
        def send_document(self, delivery, *, filename, pdf_bytes, caption):
            calls.append(filename)
            return ProviderResult(True, provider_id="f1")

        def send(self, delivery, rendered):
            raise AssertionError("text fallback must not be used when the PDF is accepted")
    delivery = SimpleNamespace(envelope=SimpleNamespace(recipient_id=3), makerspace_id=1)
    assert send_document(Provider(), delivery, {"text": "Your receipt"}).accepted
    assert calls == ["receipt.pdf"]


@pytest.mark.django_db
def test_a_brand_new_space_has_nothing_to_enable_for_chat_pdfs():
    from apps.makerspaces.models import Makerspace
    space = Makerspace.objects.create(name="Fresh", slug="fresh-pdfs")
    assert not [key for key in space.enabled_features if "chat" in key and "pdf" in key]
