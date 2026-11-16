"""Validate curated website inputs before writes or private object copies."""

from copy import deepcopy

import pytest
from rest_framework.exceptions import ValidationError

from apps.events.serializers_website import WebsiteContentInput, WebsiteSectionInput
from apps.events.services_website import save_content
from tests.events.website_helpers import content, section, website_fixture
from tests.events.website_parity_helpers import LAYOUT, metadata, venue


@pytest.mark.parametrize("field", ["website_url", "linkedin_url", "x_url"])
@pytest.mark.parametrize("value", ["javascript:alert(1)", "ftp://speaker.example/photo", "//speaker.example", "data:text/html,hello"])
def test_profile_links_only_accept_http_or_https(field, value):
    serializer = WebsiteSectionInput(data=section("speaker", "speaker", **{field: value}))
    assert not serializer.is_valid()
    assert field in serializer.errors


@pytest.mark.parametrize("scheme", ["https", "http"])
def test_profile_links_accept_web_links_and_blanks(scheme):
    serializer = WebsiteSectionInput(data=section("speaker", "speaker",
        website_url=f"{scheme}://speaker.example", linkedin_url="", x_url=""))
    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize("tier", ["platinum", "gold", "silver", "partner", "community_partner"])
def test_all_sponsor_tiers_are_accepted(tier):
    serializer = WebsiteSectionInput(data=section("sponsor", "sponsor", sponsor_tier=tier))
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["sponsor_tier"] == tier


@pytest.mark.parametrize("value", ["diamond", "GOLD", "", None])
def test_unknown_sponsor_tiers_are_rejected(value):
    serializer = WebsiteSectionInput(data=section("sponsor", "sponsor", sponsor_tier=value))
    assert not serializer.is_valid()
    assert "sponsor_tier" in serializer.errors


@pytest.mark.parametrize("color", ["#abc", "#ABCDEF", "#123456", ""])
def test_accent_accepts_only_supported_hex_forms(color):
    serializer = WebsiteContentInput(data={"revision": 1, "sections": [], "sessions": [], "accent_color": color})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize("color", ["red", "#1234", "#12345678", "123456", "#gggggg", "#abc;", "#ab\nc"])
def test_invalid_accent_is_rejected(color):
    serializer = WebsiteContentInput(data={"revision": 1, "sections": [], "sessions": [], "accent_color": color})
    assert not serializer.is_valid()
    assert "accent_color" in serializer.errors


@pytest.mark.parametrize("field,value", [
    ("latitude", -90.001), ("latitude", 90.001), ("longitude", -180.001), ("longitude", 180.001),
    ("latitude", float("nan")), ("longitude", float("inf")), ("latitude", float("-inf")),
    ("map_url", "ftp://maps.example/hall"), ("map_url", "javascript:alert(1)"),
    ("address", []), ("unknown_private_key", "not a venue field"),
])
def test_venue_rejects_bad_coordinates_links_and_unknown_fields(field, value):
    data = {"revision": 1, "sections": [], "sessions": [], "venue": {**venue(), field: value}}
    serializer = WebsiteContentInput(data=data)
    assert not serializer.is_valid()
    assert "venue" in serializer.errors


@pytest.mark.parametrize("latitude,longitude", [(-90, -180), (90, 180), (None, None)])
def test_venue_accepts_boundary_coordinates_and_unknown_coordinates(latitude, longitude):
    serializer = WebsiteContentInput(data={"revision": 1, "sections": [], "sessions": [],
        "venue": {**venue(), "latitude": latitude, "longitude": longitude}})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize("order", [LAYOUT[:-2], [*LAYOUT[:-1], "HERO"], [*LAYOUT[:-1], "CUSTOM"], "HERO"])
def test_layout_must_order_each_known_section_exactly_once(order):
    serializer = WebsiteContentInput(data={"revision": 1, "sections": [], "sessions": [], "section_order": order})
    assert not serializer.is_valid()
    assert "section_order" in serializer.errors


def test_legacy_order_omitting_only_editorial_is_upgraded():
    serializer = WebsiteContentInput(data={"revision": 1, "sections": [], "sessions": [], "section_order": LAYOUT[:-1]})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["section_order"] == LAYOUT


@pytest.mark.parametrize("toggles", [{"UNKNOWN": True}, {"SPEAKERS": "maybe"}, []])
def test_layout_toggles_reject_unknown_names_and_non_boolean_values(toggles):
    serializer = WebsiteContentInput(data={"revision": 1, "sections": [], "sessions": [], "section_enabled": toggles})
    assert not serializer.is_valid()
    assert "section_enabled" in serializer.errors


def test_bounded_highlight_icon_and_description_use_existing_editorial_fields():
    serializer = WebsiteSectionInput(data=section("workshops", "highlight", icon="wrench", body="Make something."))
    assert serializer.is_valid(), serializer.errors
    serializer = WebsiteSectionInput(data=section("workshops", "highlight", icon="w" * 41))
    assert not serializer.is_valid()
    assert "icon" in serializer.errors


@pytest.mark.django_db(transaction=True)
def test_room_limit_includes_drafts_and_invalid_save_is_atomic():
    _, actor, event, page, _ = website_fixture()
    rooms = [section(f"room-{n}", "room", visibility="draft") for n in range(30)]
    save_content(event, actor=actor, data={**content(page, rooms), **metadata()})
    page.refresh_from_db()
    previous = deepcopy(metadata())
    with pytest.raises(ValidationError):
        save_content(event, actor=actor, data={**content(page, [*rooms, section("overflow", "room")]),
                                             **previous, "tagline": "Must roll back"})
    page.refresh_from_db()
    assert page.sections.count() == 30
    assert page.tagline == previous["tagline"]
    assert page.revision == 2
