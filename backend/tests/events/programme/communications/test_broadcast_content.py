"""The composer never interprets input as executable templates or HTML."""

from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from apps.events.programme.broadcast_content import font_faces, pack, render_content, validate_ctas
from apps.events.serializers_broadcasts import BroadcastScheduleSerializer, BroadcastTestSerializer


@pytest.mark.parametrize("body", [
    "{% include 'private' %}", "{{ account.password }}", "{{ ticket_token }}",
    "<script>alert(1)</script>", "![tracker](https://example.test/image)",
    "[Credential](javascript:alert(1))", "[x]: https://example.test",
])
def test_template_html_images_and_untyped_links_refuse(body):
    with pytest.raises(ValidationError):
        pack("Notice", body, ctas=[], design="classic")


@pytest.mark.parametrize("url", [
    "http://example.test", "javascript:alert(1)", "https://user:pass@example.test/",
    "https://example.test/?token=secret", "https://example.test/#bearer",
    "https://example.test/invite/secret", "https://example.test/checkin/secret",
    "https://example.test/%74oken/private", "https://example.test/path%0aevil",
])
def test_ctas_cannot_transport_credentials(url):
    with pytest.raises(ValidationError):
        validate_ctas([{"kind": "https", "label": "Read", "url": url}])


def test_data_only_merge_and_three_brand_designs():
    context = {"name": '<img src=x onerror="alert(1)">', "event_title": "Make",
        "event_date": "2026-10-18", "event_location": "Lab", "ticket_url": "/member/events/1/ticket",
        "event_url": "/events/public"}
    for design in ("classic", "bold", "minimal"):
        campaign = SimpleNamespace(render_schema_version=2, design=design, subject="Hello {{ name }}",
            body=pack("Hello {{ name }}", "**Welcome** {{ name }}\n\n- One\n- Two", design=design,
                      ctas=[{"kind": "navigation", "label": "My ticket", "target": "ticket"}]))
        rendered = render_content(campaign, context, preview=True)
        assert "<img" not in rendered["html_body"]
        assert "<script" not in rendered["html_body"]
        assert '<strong>Welcome</strong>' in rendered["html_body"]
        assert '<ul><li>One</li><li>Two</li></ul>' in rendered["html_body"]
        assert "/member/events/1/ticket" in rendered["text_body"]
        assert "Space Works" in rendered["html_body"]
        for family, face, weight in (("Outfit", "Outfit-Variable", "400 700"), ("Gilroy", "Gilroy-ExtraBold", "800")):
            assert f'font-family:"{family}";src:url("/fonts/{face}.woff2") format("woff2")' in rendered["html_body"]
            assert f'font-weight:{weight};font-display:swap' in rendered["html_body"]
        assert rendered["html_body"].count("@font-face") == 2
        # Only the free Gilroy weight ships; the commercial 400-700 files are gone.
        for face in ("Regular", "Medium", "SemiBold", "Bold"):
            assert f"Gilroy-{face}" not in rendered["html_body"]
        assert "prefers-color-scheme:dark" in rendered["html_body"]


def test_email_fonts_use_only_configured_frontend_origin(settings):
    settings.PUBLIC_APP_BASE_URL = "https://spaceworks.example.test/app"
    assert 'url("https://spaceworks.example.test/fonts/Outfit-Variable.woff2")' in font_faces(preview=False)
    assert 'url("/fonts/Outfit-Variable.woff2")' in font_faces(preview=True)
    settings.PUBLIC_APP_BASE_URL = 'https://spaceworks.example.test/\";url(https://other.test)'
    assert "other.test" not in font_faces(preview=False)


def test_ctas_maximum_and_closed_self_test_input():
    with pytest.raises(ValidationError):
        validate_ctas([{"kind": "navigation", "label": "Read", "target": "event"}] * 4)
    serializer = BroadcastTestSerializer(data={"operation_id": "00000000-0000-0000-0000-000000000001",
        "expected_version": 1, "preview_id": 1, "to_email": "someone@example.test"})
    assert not serializer.is_valid()
    assert serializer.errors["code"] == "unknown_fields"
    schedule = BroadcastScheduleSerializer(data={"operation_id": "00000000-0000-0000-0000-000000000001",
        "expected_version": 1, "preview_id": 1, "revision": "not-a-revision", "confirm": True,
        "recipient_count": 1, "available_at": "2026-10-18T00:00:00Z"})
    assert not schedule.is_valid()


@pytest.mark.parametrize("kind", [{}, [], 1, None])
def test_malformed_cta_kind_returns_validation_error(kind):
    with pytest.raises(ValidationError):
        validate_ctas([{"kind": kind, "label": "Read", "target": "event"}])


def test_legacy_body_keeps_plaintext_wire_shape():
    campaign = SimpleNamespace(render_schema_version=1, body="{{ name }}", subject="Hello")
    result = render_content(campaign, {"name": "Maker"})
    assert result["text_body"] == "Maker"
