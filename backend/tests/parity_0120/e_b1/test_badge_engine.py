"""E-B1: badge_v1 in the card engine: recompile on save, the lock, convert, domain rules, role resolution,
the routes and their switches, and the 6x4 render size."""
from io import BytesIO

import pytest
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.card_designs import badge_format, designs, layout, resolution, resolution_roles
from apps.card_designs.badge_source import BadgeFormatLocked, without_source
from apps.card_designs.models import CardDesign
from tests.l3_local.helpers import card_event, card_space, client, manager

pytestmark = pytest.mark.django_db
FEATURES = ("events.id_cards", "events.badge_designer", "events.role_badges")


def _source(**settings):
    return {"version": 2, "source": {"format": "badge_v1",
                                     "settings": badge_format.normalize({"colorMode": "colour", **settings})}}


def _setup(slug, features=FEATURES):
    space = card_space(slug, features=features)
    return space, card_event(space), manager(space)


def _turn_off(space, key):
    space.enabled_features = [feature for feature in space.enabled_features if feature != key]
    space.save(update_fields=["enabled_features", "updated_at"])


def _role(user, event, role, body=None):
    return client(user).post(f"/api/v1/admin/events/{event.pk}/badge-designs/{role}", body or {}, format="json")


def test_normalize_document_compiles_the_front_and_ignores_smuggled_layers():
    document = _source()
    document["front"] = {"layers": [{"id": "x", "kind": "text", "text": "smuggled"}]}
    clean = layout.normalize_document(document, check_contrast=False)
    assert clean["source"]["format"] == "badge_v1" and clean["back_enabled"] is False
    assert not any(layer.get("text") == "smuggled" for layer in clean["front"]["layers"])
    assert any(layer["kind"] == "checkin_qr" for layer in clean["front"]["layers"])
    assert layout.normalize_document(clean, check_contrast=False) == clean  # idempotent


def test_a_wrong_source_format_or_unknown_setting_is_refused():
    for source in ({"format": "other", "settings": {}}, {"format": "badge_v1", "settings": {"nope": 1}}):
        with pytest.raises(ValidationError):
            layout.normalize_document({"version": 2, "source": source}, check_contrast=False)


def test_badge_source_and_checkin_qr_are_event_card_only():
    space = card_space("eb1-domain")
    free = without_source(layout.normalize_document(_source(), check_contrast=False))
    designs.validated(space.pk, free, check_contrast=False, domain="event_card")
    for domain in ("member_cards", "event_ticket", "id_programme"):
        with pytest.raises(ValidationError):
            designs.validated(space.pk, free, check_contrast=False, domain=domain)
        with pytest.raises(ValidationError):
            designs.validated(space.pk, _source(), check_contrast=False, domain=domain)


def test_a_badge_design_is_locked_until_converted():
    space, event, sm = _setup("eb1-lock")
    row = _role(sm, event, "attendee")
    assert row.status_code == 200 and row.json()["design"]["badge_format"] == "badge_v1"
    design = CardDesign.objects.get(pk=row.json()["design"]["id"])
    with pytest.raises(BadgeFormatLocked):
        designs.save(sm, design, without_source(design.document), expected_revision=design.revision)
    converted = client(sm).post(f"/api/v1/admin/card-designs/{design.pk}/convert-to-free-canvas")
    assert converted.status_code == 200 and converted.json()["badge_format"] is None
    assert AuditLog.objects.filter(action="card_design.badge_converted").exists()
    again = client(sm).post(f"/api/v1/admin/card-designs/{design.pk}/convert-to-free-canvas")
    assert again.status_code == 400


def test_role_variants_resolve_the_role_design_then_fall_back_to_attendee():
    space, event, sm = _setup("eb1-roles")
    base = CardDesign.objects.get(pk=_role(sm, event, "attendee").json()["design"]["id"])
    designs.publish(sm, base)
    crew = CardDesign.objects.get(pk=_role(sm, event, "crew").json()["design"]["id"])
    assert crew.card_role == "crew" and crew.document["source"]["settings"]["badgeLabel"] == "CREW"
    assert resolution_roles.resolve_event_card(space.pk, event.pk, None, [], "crew")[1].pk == base.pk  # unpublished
    designs.publish(sm, crew)
    assert resolution_roles.resolve_event_card(space.pk, event.pk, None, [], "crew")[1].pk == crew.pk
    assert resolution_roles.resolve_event_card(space.pk, event.pk, None, [], "speaker")[1].pk == base.pk
    assert resolution_roles.resolve_event_card(space.pk, event.pk, None, [], "attendee")[1].pk == base.pk
    assert resolution.resolve(space.pk, "event_card", event_id=event.pk)[1].pk == base.pk  # plain chain skips roles
    assert AuditLog.objects.filter(action="card_design.role_variant_created").exists()


def test_a_role_variant_is_unique_per_event_and_role():
    space, event, sm = _setup("eb1-unique")
    first = _role(sm, event, "mentor").json()
    second = _role(sm, event, "mentor").json()
    assert first["created"] is True and second["created"] is False and first["design"]["id"] == second["design"]["id"]
    assert CardDesign.objects.filter(event=event, card_role="mentor").count() == 1


def test_switches_off_answer_404_and_role_resolution_falls_back():
    space, event, sm = _setup("eb1-off")
    base = CardDesign.objects.get(pk=_role(sm, event, "attendee").json()["design"]["id"])
    designs.publish(sm, base)
    crew = CardDesign.objects.get(pk=_role(sm, event, "crew").json()["design"]["id"])
    designs.publish(sm, crew)
    _turn_off(space, "events.role_badges")
    assert _role(sm, event, "crew").status_code == 404
    assert resolution_roles.resolve_event_card(space.pk, event.pk, None, [], "crew")[1].pk == base.pk
    _turn_off(space, "events.badge_designer")
    assert client(sm).get(f"/api/v1/admin/events/{event.pk}/badge-designs").status_code == 404
    assert client(sm).get(f"/api/v1/admin/card-designs/{base.pk}/badge-export").status_code == 404


def test_unknown_role_and_other_tenants_are_404():
    space, event, sm = _setup("eb1-404")
    assert _role(sm, event, "wizard").status_code == 404
    _other_space, _other_event, other_sm = _setup("eb1-404-other")
    assert _role(other_sm, event, "attendee").status_code in (403, 404)


def test_import_route_accepts_an_events_file_and_reports_unmatched_answers():
    space, event, sm = _setup("eb1-import")
    design_id = _role(sm, event, "attendee").json()["design"]["id"]
    file = {"kind": "swe-id-card-design", "version": 2,
            "settings": {"template": "minimal", "colorMode": "colour", "printFieldKeys": ["abc123"],
                         "printFieldLabels": {"abc123": "Company"}, "unknownThing": 1}}
    response = client(sm).post(f"/api/v1/admin/card-designs/{design_id}/badge-import", {"file": file}, format="json")
    body = response.json()
    assert response.status_code == 200 and body["design"]["document"]["source"]["settings"]["template"] == "minimal"
    assert body["unmatched_fields"] == ["abc123"] and body["notes"]
    exported = client(sm).get(f"/api/v1/admin/card-designs/{design_id}/badge-export")
    assert exported.status_code == 200 and exported.json()["kind"] == "spaceworks-event-badge"


def test_designs_list_describes_roles_fields_and_presets():
    space, event, sm = _setup("eb1-list")
    _role(sm, event, "attendee")
    body = client(sm).get(f"/api/v1/admin/events/{event.pk}/badge-designs").json()
    assert [row["role"] for row in body["roles"]][:2] == ["attendee", "crew"]
    assert body["roles"][0]["format"] == "badge_v1" and body["roles"][1]["format"] == "none"
    assert [field["key"] for field in body["fields"]][-2:] == ["attendee:team", "attendee:crew_kind"]
    assert body["max_print_fields"] == 8 and {p["id"] for p in body["presets"]} == {"a6", "4x6", "3x4", "4x3", "cr80"}


def test_a_six_by_four_badge_renders_at_300_dpi():
    from PIL import Image
    from apps.card_designs.cards import sample_context
    from apps.card_designs.rendering import render_png
    space = card_space("eb1-6x4")
    document = layout.normalize_document(_source(widthMm=152.4, heightMm=101.6), check_contrast=False)
    png = render_png(document, sample_context(space, document))
    assert Image.open(BytesIO(png)).size == (1800, 1200)


def test_an_event_answer_and_email_preview_with_sample_values():
    from apps.card_designs.cards import sample_context
    space = card_space("eb1-sample")
    document = layout.normalize_document(_source(printFieldKeys=["registration:company"]), check_contrast=False)
    values = sample_context(space, document).values
    assert values["field:company"] == "Sample answer" and values["email"] and values["crew_kind"]
