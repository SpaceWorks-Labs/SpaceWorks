"""E-B1: the badge_v1 settings normaliser, Events design files and the shared normalise fixtures."""
import copy

import pytest
from rest_framework.exceptions import ValidationError

from apps.card_designs import badge_format, badge_import
from tests.parity_0120.e_b1.fixture_files import load

EVENTS_FILE = {"kind": "swe-id-card-design", "version": 2, "settings": {
    "widthMm": 105, "heightMm": 148, "heading": "Hack Night", "badgeLabel": "ATTENDEE", "showEmail": True,
    "template": "bold", "footerText": "Makers", "showLogo": True, "printFieldKeys": ["registration:company"],
    "printFieldLabels": {"registration:company": "Organisation"}, "colorMode": "colour", "backgroundColor": "cream",
    "accentColor": "event", "textColor": "auto", "showEventLogo": False, "showSymbol": True, "showPhoto": False,
    "photoShape": "circle", "showSponsors": False, "sponsorLimit": 4, "showName": True, "showQr": True,
    "watermark": {"kind": "text", "text": "Staff", "opacityPct": 10, "colour": "accent", "angleDeg": -30},
    "notAKey": 1}}


@pytest.mark.parametrize("case", load("badge_normalize_cases.json"), ids=lambda case: case["id"])
def test_normalize_matches_the_shared_fixture(case):
    assert badge_format.normalize(case["input"], event_title="Spring Build Night",
                                  organisation_name="Tinkerspace") == case["settings"]


def test_normalize_is_idempotent():
    for case in load("badge_normalize_cases.json"):
        once = case["settings"]
        assert badge_format.normalize(copy.deepcopy(once)) == once


def test_strict_rejects_unknown_keys_and_oversize_json():
    with pytest.raises(ValidationError):
        badge_format.normalize({"colorMode": "colour", "smuggled": 1}, strict=True)
    with pytest.raises(ValidationError):
        badge_format.normalize({"colorMode": "colour", "heading": "x" * 40_000}, strict=True)
    with pytest.raises(ValidationError):
        badge_format.normalize("nope", strict=True)


def test_positions_and_sizes_are_clamped_to_the_card():
    settings = badge_format.normalize({"colorMode": "colour", "widthMm": 105, "heightMm": 148,
                                       "elementPositions": {"qr": {"xMm": 9999, "yMm": 9999}},
                                       "elementSizes": {"qr": 9999}})
    qr, size = settings["elementPositions"]["qr"], settings["elementSizes"]["qr"]
    assert size <= 101 and qr["xMm"] + size <= 105 and qr["yMm"] + size <= 148


def test_events_design_file_imports_as_written_and_notes_what_it_drops():
    settings, notes = badge_import.parse(EVENTS_FILE, event_title="Spring", organisation_name="Guild")
    assert settings["template"] == "bold" and settings["printFieldKeys"] == ["registration:company"]
    assert settings["printFieldLabels"] == {"registration:company": "Organisation"}
    assert any("notAKey" in note for note in notes)


@pytest.mark.parametrize("kind", ["swe-id-card-design", "yuyu-id-card-design"])
def test_both_events_kinds_are_accepted_and_native_round_trips(kind):
    settings, _notes = badge_import.parse({**EVENTS_FILE, "kind": kind})
    again, _ = badge_import.parse(badge_import.export(settings))
    assert again == settings


def test_import_refuses_other_files_and_newer_native_versions():
    for bad in ('{"kind": "x"}', "not json", {"kind": "spaceworks-event-badge", "version": 2, "settings": {}},
                {"kind": "swe-id-card-design", "settings": []}):
        with pytest.raises(ValidationError):
            badge_import.parse(bad)


def test_import_caps_answers_at_eight_and_drops_an_image_watermark():
    file = copy.deepcopy(EVENTS_FILE)
    file["settings"]["printFieldKeys"] = [f"registration:k{i}" for i in range(12)]
    file["settings"]["watermark"] = {"kind": "image", "opacityPct": 10}
    settings, notes = badge_import.parse(file)
    assert len(settings["printFieldKeys"]) == 8 and settings["watermark"]["kind"] == "none" and len(notes) >= 3
