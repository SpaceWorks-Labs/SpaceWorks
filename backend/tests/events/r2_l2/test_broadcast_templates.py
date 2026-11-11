"""G6: starter templates, the four new placeholders and the three new brand designs."""

import pytest as _legacy_pytest

_legacy_pytest.skip('Not in release 0.12.0: apps.events.registration_access.EventRegistration', allow_module_level=True)

from types import SimpleNamespace
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.events.programme.broadcast_content import DESIGNS, PLACEHOLDERS, pack, render_content
from apps.events.programme.broadcast_placeholders import placeholder_context
from apps.events.registration_access import EventRegistration
from apps.integrations.broadcasts_templates import EVENT_STARTER_TEMPLATES, validate_strings
from tests.events.lane_d_helpers import fixture

pytestmark = pytest.mark.django_db


def test_thirteen_templates_use_only_known_placeholders_designs_and_statuses():
    assert len(EVENT_STARTER_TEMPLATES) == 13
    assert len({row["key"] for row in EVENT_STARTER_TEMPLATES}) == 13
    for row in EVENT_STARTER_TEMPLATES:
        validate_strings(row["subject"], row["body"], PLACEHOLDERS)
        pack(row["subject"], row["body"], ctas=[], design=row["design"])
        assert set(row["statuses"]) <= set(EventRegistration.Status.values)
        assert row["attendance"] in {"any", "attended", "not_attended"}
        assert row["design"] in DESIGNS
    assert {"event_url", "feedback_url", "schedule_url", "organization"} <= set(PLACEHOLDERS)


def test_new_placeholders_render_public_navigation_only(monkeypatch):
    space, actor, member, event, registration = fixture(monkeypatch)
    context = placeholder_context(event, name="Ada", ticket_url="https://example.test/ticket")
    token = str(event.public_token)
    assert context["feedback_url"].endswith(f"/events/{token}/feedback")
    assert context["schedule_url"].endswith(f"/events/{token}/schedule")
    assert context["event_url"].endswith(f"/e/{token}")
    assert context["organization"] == space.name
    assert str(registration.checkin_token) not in "".join(context.values())


def test_organization_placeholder_names_the_active_cohost(monkeypatch):
    from apps.events.organizer_models import EventOrganizer
    from apps.organizations.models import Organization
    space, actor, member, event, registration = fixture(monkeypatch)
    org = Organization.objects.create(name="Circuit Club", slug=f"circuit-{uuid4().hex[:6]}")
    EventOrganizer.objects.create(event=event, organization=org)
    assert placeholder_context(event, name="x", ticket_url="u")["organization"] == "Circuit Club"
    Organization.objects.filter(pk=org.pk).update(is_active=False)
    assert placeholder_context(event, name="x", ticket_url="u")["organization"] == space.name


@pytest.mark.parametrize("design", ["accent_band", "photo_header", "letter"])
def test_new_designs_render_brand_only_html_in_light_and_dark(design):
    body = pack("Hi {{ name }}", "**Welcome** {{ name }}", ctas=[], design=design)
    campaign = SimpleNamespace(render_schema_version=2, design=design, subject="Hi {{ name }}", body=body)
    rendered = render_content(campaign, {key: "<b>x</b>" for key in PLACEHOLDERS}, preview=True)
    html = rendered["html_body"]
    assert "<script" not in html and "<b>x</b>" not in html
    assert "prefers-color-scheme:dark" in html and "Gilroy" in html
    assert "#FFF4E8" in html and "#142C2A" in html
    if design == "photo_header":
        assert 'class="cover-fallback"' in html  # no event: brand band instead of a photo
    if design == "letter":
        assert 'class="signature"' in html and "&lt;b&gt;x&lt;/b&gt;" in html


def test_templates_endpoint_requires_event_authority(monkeypatch):
    space, actor, member, event, registration = fixture(monkeypatch)
    client = APIClient()
    client.force_authenticate(member)
    path = f"/api/v1/admin/events/{event.pk}/broadcast-templates/"
    assert client.get(path).status_code in {403, 404}
    client.force_authenticate(actor)
    response = client.get(path)
    assert response.status_code == 200, response.content
    assert len(response.json()) == 13 and response.json()[0]["key"] == "welcome"
