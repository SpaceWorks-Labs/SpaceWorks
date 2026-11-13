"""MOD-3 flow audit: every membership and payments email template, rendered for real.

Per template: renders in every supported locale (translated default, English fallback), leaves no
unresolved template syntax, has a single-line subject (no header injection), escapes hostile text
in the context, and a tenant's edited row never leaks into another makerspace's mail.
"""
import pytest
from django.utils import translation

from apps.integrations import email_templates
from apps.integrations.email_templates_registry import iter_entries
from apps.integrations.models import EmailTemplate
from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db

MY_STREAMS = {"membership", "payments"}
ENTRIES = [(key, entry) for key, entry in iter_entries() if key[0] in MY_STREAMS]


def _space(slug, name):
    return Makerspace.objects.create(name=name, slug=slug)


def test_the_membership_and_payment_templates_are_not_empty_set():
    streams = {key[0] for key, _ in ENTRIES}
    assert streams == MY_STREAMS
    assert len(ENTRIES) >= 10


@pytest.mark.parametrize("key,entry", ENTRIES, ids=["/".join(key) for key, _ in ENTRIES])
def test_each_template_renders_in_every_locale_without_leaks(key, entry):
    from django.conf import settings
    space = _space("mod3-mail-a", "Alpha Space")
    for code, _label in settings.LANGUAGES:
        with translation.override(code):
            out = email_templates.render(space, *key, dict(entry.sample_context))
        assert out["subject"] and "\n" not in out["subject"] and "\r" not in out["subject"], (key, code)
        for part in ("subject", "text_body", "html_body"):
            assert "{{" not in out[part] and "{%" not in out[part], (key, code, part)


@pytest.mark.parametrize("key,entry", ENTRIES, ids=["/".join(key) for key, _ in ENTRIES])
def test_hostile_context_text_is_escaped_in_html_and_cannot_break_the_subject(key, entry):
    space = _space("mod3-mail-b", "Beta Space")
    hostile = "<script>alert(1)</script>\r\nBcc: evil@example.test"
    context = {name: (hostile if isinstance(value, str) else value) for name, value in dict(entry.sample_context).items()}
    out = email_templates.render(space, *key, context)
    assert "<script>" not in out["html_body"]
    assert "\n" not in out["subject"] and "\r" not in out["subject"]


def test_a_tenants_edited_template_never_applies_to_another_makerspace():
    a, b = _space("mod3-mail-c", "Gamma"), _space("mod3-mail-d", "Delta")
    (stream, audience, name), entry = ENTRIES[0]
    EmailTemplate.objects.create(makerspace=a, stream=stream, audience=audience, key=name, is_active=True,
                                 subject="GAMMA-ONLY subject", text_body="GAMMA-ONLY body", html_body="")
    context = dict(entry.sample_context)
    assert email_templates.render(a, stream, audience, name, context)["subject"] == "GAMMA-ONLY subject"
    other = email_templates.render(b, stream, audience, name, context)
    assert "GAMMA-ONLY" not in other["subject"] + other["text_body"] + other["html_body"]


def test_a_broken_stored_row_falls_back_to_the_default_instead_of_failing_the_send():
    space = _space("mod3-mail-e", "Epsilon")
    (stream, audience, name), entry = ENTRIES[0]
    EmailTemplate.objects.create(makerspace=space, stream=stream, audience=audience, key=name, is_active=True,
                                 subject="{% bogus %}", text_body="{% if %}", html_body="")
    out = email_templates.render(space, stream, audience, name, dict(entry.sample_context))
    assert out["subject"] and "{%" not in out["subject"]
