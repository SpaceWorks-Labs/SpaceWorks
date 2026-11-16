"""Email template defaults render per recipient locale; edited tenant rows stay byte-for-byte."""
from pathlib import Path
from unittest import mock

import pytest

from apps.integrations import email_templates
from apps.integrations.email_templates_registry import get_entry
from apps.integrations.models import EmailTemplate
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db
CONTEXT = {"makerspace": {"name": "Demo"}, "request": {"id": 7, "status": "pending"}}
PO = Path(__file__).resolve().parents[2] / "locale/en/LC_MESSAGES/django.po"


def test_default_goes_through_gettext_in_the_recipient_override():
    space = make_space("i18n-template-default")
    user = make_user("i18n-template-user")
    entry = get_entry("hardware", "requester", "request_received")
    with mock.patch.object(email_templates, "gettext", side_effect=lambda value: value) as spy, \
            mock.patch.object(email_templates, "override_for", wraps=email_templates.override_for) as scope:
        rendered = email_templates.render(space, "hardware", "requester", "request_received", CONTEXT,
                                          recipient=lambda: user)
    assert mock.call(entry.default_subject) in spy.call_args_list
    assert scope.call_args.kwargs["makerspace"] == space
    assert rendered["subject"] == "Demo request received"


def test_edited_tenant_row_is_byte_for_byte():
    space = make_space("i18n-template-edited")
    subject = "Rückmeldung {{ makerspace.name }} — #{{ request.id }}"
    EmailTemplate.objects.create(makerspace=space, stream="hardware", audience="requester", key="request_received",
                                 subject=subject, text_body="Body {{ request.status }}", html_body="", is_active=True)
    with mock.patch.object(email_templates, "gettext") as spy:
        rendered = email_templates.render(space, "hardware", "requester", "request_received", CONTEXT)
    spy.assert_not_called()
    assert rendered["subject"] == "Rückmeldung Demo — #7"
    assert rendered["text_body"] == "Body pending"


def test_registry_defaults_are_catalogue_entries():
    text = PO.read_text(encoding="utf-8")
    entry = get_entry("hardware", "requester", "request_received")
    assert f'msgid "{entry.default_subject}"' in text


def test_empty_default_html_never_returns_the_catalogue_header():
    assert email_templates._translated("") == ""
