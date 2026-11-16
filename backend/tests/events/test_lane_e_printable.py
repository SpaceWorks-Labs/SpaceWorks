from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from reportlab.pdfgen.canvas import Canvas
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.events.badge_templates import normalize_badge_template
from apps.events.badge_rendering import render_badges_pdf
from apps.events.models import EventRegistration
from apps.events.services_badges import BadgeSnapshot, prepare_badges
from apps.operations.printable_fonts import font_markup
from apps.operations.printable_layout import normalize_element
from apps.operations.printable_pdf import text_box
from tests.events.checkin_helpers import register
from tests.events.staff_grant_helpers import grant_fixture, set_grant_permissions
from tests.events.ticketing_helpers import account


def test_v1_converts_on_read_without_changing_source_or_printing_qr():
    source = {"version": 1, "fields": ["name"], "include_qr": True}
    original = deepcopy(source)
    result = normalize_badge_template(source, SimpleNamespace(custom_form=[]))
    assert source == original
    assert result["version"] == 2 and len(result["elements"]) == 1
    assert result["include_qr"] is False


@pytest.mark.parametrize("field", ["email", "phone", "checkin_token", "custom:absent"])
def test_contact_credentials_and_unknown_answers_refused(field):
    with pytest.raises(ValidationError):
        normalize_badge_template({"fields": [field]}, SimpleNamespace(custom_form=[]))


def test_grid_bounds_font_range_and_invalid_binding():
    element = {"field": "name", "x_mm": 3.6, "y_mm": 2.1, "width_mm": 30, "height_mm": 10,
               "font_size_pt": 48, "bold": True}
    normalized = normalize_element(element, width=90, height=55, fields={"name"}, grid_mm=2)
    assert (normalized["x_mm"], normalized["y_mm"]) == (4, 2)
    for changed in ({"font_size_pt": 49}, {"x_mm": 89}, {"font": "../../file.ttf"},
                    {"field": []}, {"colour": "red"}, {"bold": "yes"}, {"x_mm": float("inf")}):
        with pytest.raises(ValidationError):
            normalize_element(element | changed, width=90, height=55, fields={"name"})


def badge_snapshot(fields):
    """The typed, keyword-only print snapshot the service builds (legacy sheet stock)."""
    from datetime import timedelta
    from django.utils import timezone
    now = timezone.now()
    return BadgeSnapshot(
        registration_id=1, event_id=1, member_id=None, authorized_fields=fields,
        template_revision="0" * 64, stock="legacy-sheet", logo_artwork_revision=None,
        credential_generation=None, credential_render_handle=None, presentation_id=None,
        presentation_version=None, source_profile_id=None, source_avatar_revision=None,
        photo_sha256=None, photo_render_handle=None, created_at=now, expires_at=now + timedelta(minutes=5),
    )


@pytest.mark.parametrize("text", ['Zo\xeb Fran\xe7ois', '\u0928\u092e\u0938\u094d\u0924\u0947 \u0926\u0941\u0928\u093f\u092f\u093e', '\u4e2d\u6587\u59d3\u540d', '\u0645\u0631\u062d\u0628\u0627 \u0628\u0627\u0644\u0639\u0627\u0644\u0645', '\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd'])
def test_unicode_fallback_and_actual_pdf(text):
    event = SimpleNamespace(custom_form=[])
    template = normalize_badge_template({"fields": ["name"]}, event)
    markup = font_markup(text, "sans", False)
    assert "Print-" in markup or "STSong-Light" in markup
    payload = render_badges_pdf(template, [badge_snapshot((("Name", text),))], title="Unicode badge")
    assert payload.startswith(b"%PDF") and len(payload) > 1000


def test_overflow_refuses_instead_of_dropping_text():
    element = normalize_element({"field": "name", "x_mm": 0, "y_mm": 0, "width_mm": 1,
                                "height_mm": 1, "font_size_pt": 6}, width=90, height=55, fields={"name"})
    with pytest.raises(ValidationError, match="does not fit"):
        text_box(Canvas(BytesIO()), "A long recipient name", element, area_height_mm=55)


@pytest.mark.parametrize("text", ["W", "W\u4e2d", "\u4e2dW", "\u4e2d"])
def test_horizontal_overflow_refuses_even_when_line_height_fits(text):
    element = normalize_element({"field": "name", "x_mm": 0, "y_mm": 0, "width_mm": 1,
                                "height_mm": 20, "font_size_pt": 6}, width=90, height=55, fields={"name"})
    canvas = Mock()
    with pytest.raises(ValidationError, match="does not fit"):
        text_box(canvas, text, element, area_height_mm=55)
    canvas.saveState.assert_not_called()


@pytest.mark.parametrize("text", ["W\u4e2d", "\u4e2dW"])
def test_mixed_cjk_text_renders_and_shrinks_within_actual_width(text, monkeypatch):
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph

    drawn = []
    monkeypatch.setattr(Paragraph, "drawOn", lambda paragraph, *args: drawn.append(paragraph))
    element = normalize_element({"field": "name", "x_mm": 0, "y_mm": 0, "width_mm": 5,
                                "height_mm": 3, "font_size_pt": 24}, width=90, height=55, fields={"name"})
    text_box(Canvas(BytesIO()), text, element, area_height_mm=55)
    assert len(drawn) == 1
    paragraph = drawn[0]
    assert 6 <= paragraph.style.fontSize < 24
    assert paragraph.height <= 3 * mm
    assert all(line.extraSpace >= -1e-6 for line in paragraph.blPara.lines)
    assert paragraph.getPlainText() == text


def test_separate_cjk_word_keeps_other_words_shapable(monkeypatch):
    from reportlab.platypus import Paragraph

    drawn = []
    monkeypatch.setattr(Paragraph, "drawOn", lambda paragraph, *args: drawn.append(paragraph))
    element = normalize_element({"field": "name", "x_mm": 0, "y_mm": 0, "width_mm": 80,
                                "height_mm": 20, "font_size_pt": 12}, width=90, height=55, fields={"name"})
    text_box(Canvas(BytesIO()), "Workshop \u4e2d", element, area_height_mm=55)
    assert len(drawn) == 1 and drawn[0].style.shaping


def test_horizontal_overflow_shrinks_until_actual_line_width_fits(monkeypatch):
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph

    drawn = []
    monkeypatch.setattr(Paragraph, "drawOn", lambda paragraph, *args: drawn.append(paragraph))
    element = normalize_element({"field": "name", "x_mm": 0, "y_mm": 0, "width_mm": 3,
                                "height_mm": 20, "font_size_pt": 24}, width=90, height=55, fields={"name"})
    text_box(Canvas(BytesIO()), "W", element, area_height_mm=55)
    assert len(drawn) == 1
    paragraph = drawn[0]
    assert 6 <= paragraph.style.fontSize < 24
    from reportlab.pdfbase.pdfmetrics import stringWidth
    assert stringWidth("W", "Print-sans-False", paragraph.style.fontSize) <= 3 * mm


@pytest.mark.django_db
def test_checkin_only_actor_can_print_attended_safe_badge_but_not_registered():
    space, manager, user, event, grant = grant_fixture("check_in")
    attended = register(event, account("safe-attended"), status="attended")
    registered = register(event, account("still-registered"))
    template, snapshots = prepare_badges(event, [attended.pk], actor=user, include_attended=True)
    assert not hasattr(snapshots[0], "checkin_token")
    assert all("@" not in value for _label, value in snapshots[0].fields)
    with pytest.raises(PermissionDenied):
        prepare_badges(event, [registered.pk], actor=user)
    with pytest.raises(PermissionDenied):
        prepare_badges(event, [attended.pk], actor=user, include_attended=True, template_override={})


@pytest.mark.django_db
def test_answers_require_registration_authority_before_field_reads(monkeypatch):
    space, manager, user, event, grant = grant_fixture("check_in")
    event.custom_form = [{"id": "answer", "label": "Private answer", "type": "short_text",
                          "required": False, "options": []}]
    event.badge_template = {"fields": ["custom:answer"]}
    event.save()
    attendee = register(event, account("private-attendee"), status="attended")
    fields = Mock(return_value=(("Private", "answer-body"),))
    monkeypatch.setattr("apps.events.services_badges._field_values", fields)
    with pytest.raises(PermissionDenied):
        prepare_badges(event, [attendee.pk], actor=user, include_attended=True)
    fields.assert_not_called()
    set_grant_permissions(grant, ["check_in", "manage_registrations"])
    # The event's manage_registrations grant suffices; tenant VIEW_AUDIT is not required.
    granted = prepare_badges(event, [attendee.pk], actor=user, include_attended=True)
    assert granted[1][0].fields == (("Private", "answer-body"),)
    result = prepare_badges(event, [attendee.pk], actor=manager, include_attended=True)
    assert result[1][0].fields == (("Private", "answer-body"),)



def test_legacy_contact_layout_converts_to_safe_editable_fields_without_mutating_source():
    source = {"version": 1, "fields": ["email", "phone"], "include_qr": True}
    result = normalize_badge_template(source, SimpleNamespace(custom_form=[]))
    assert result["fields"] == ["name"]
    assert result["version"] == 2 and result["include_qr"] is False
    assert source["fields"] == ["email", "phone"]
