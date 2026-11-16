"""Each financial document has a personal template and no staff room entry."""
import pytest

from apps.integrations.chat_templates import chat_entry
from apps.integrations.chat_templates_catalog import PERSONAL_ONLY_EVENTS
from apps.integrations.email_templates import render_preview
from apps.integrations.email_templates_registry import get_entry


@pytest.mark.parametrize("kind,label", [("receipt", "Receipt"), ("credit_note", "Credit note"), ("bill", "Bill")])
def test_every_document_kind_has_a_valid_personal_template(kind, label):
    key = "document_" + kind
    entry = get_entry("payments", "requester", key)
    assert entry is not None
    rendered = render_preview("payments", "requester", key,
                              entry.default_subject, entry.default_text, entry.default_html)
    assert label in rendered["subject"] and "25.00" in rendered["text_body"]
    assert get_entry("payments", "staff", key) is None
    assert chat_entry("payments", key) is None
    assert ("payments", "document_issued") in PERSONAL_ONLY_EVENTS
    assert chat_entry("payments", "document_issued") is None


@pytest.mark.parametrize("variables,audience,event", [
    (["__document_media__"], "staff", "document_issued.document"),
    (["number", "__document_header__"], "requester", "document_issued.document"),
    (["__document_header__", "__document_media__"], "requester", "document_issued.document"),
    (["__document_media__"], "requester", "payment_received"),
])
def test_document_template_media_markers_are_validated_at_settings_boundary(variables, audience, event):
    from apps.integrations.notification_api_serializers import TemplateSerializer
    serializer = TemplateSerializer(data={"template_name": "approved_document", "variables": variables,
        "audience": audience, "event": event, "locale": "en"})
    assert not serializer.is_valid() and "variables" in serializer.errors
