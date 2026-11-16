"""Lane r2-gap-misc, gap 17 (S7, #180): the public gallery offers its public choice fields as filters.

Local, untracked (#175): written in the coding phase, run in the test phase on the combined tree.
The gallery list now carries ``filters`` (the final stage's public choice fields) beside the page, so
the public page can render one control per field and send ``field.<key>=<choice>``.
"""
from uuid import uuid4

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from apps.events.submissions import gallery_views
from apps.events.submissions.stage_gallery import filter_by_fields, gallery_filters
from tests.submit_content_local.stage_helpers import stage, world

pytestmark = pytest.mark.django_db

PUBLIC_TRACK = {"key": "track", "label": "Track", "type": "choice", "required": False,
                "choices": ["Health", "Climate"], "visible_to": "public"}
STAFF_TRACK = {"key": "budget", "label": "Budget", "type": "choice", "required": False,
               "choices": ["Low", "High"], "visible_to": "staff"}
PUBLIC_TEXT = {"key": "pitch", "label": "Pitch", "type": "short_text", "required": False, "visible_to": "public"}


def search(monkeypatch, on):
    monkeypatch.setattr("apps.events.judging.feature.enabled", lambda *_args: on)


def staged(monkeypatch):
    w = world(monkeypatch)
    stage(w.event, 1, custom_fields=[{**PUBLIC_TRACK, "key": "idea_track"}])
    stage(w.event, 2, custom_fields=[PUBLIC_TRACK, STAFF_TRACK, PUBLIC_TEXT])
    return w


def test_only_the_final_stages_public_choice_fields_are_offered(monkeypatch):
    w = staged(monkeypatch)
    search(monkeypatch, True)
    assert gallery_filters(w.event) == [{"key": "track", "label": "Track", "choices": ["Health", "Climate"]}]


def test_no_filters_while_gallery_search_is_off(monkeypatch):
    w = staged(monkeypatch)
    search(monkeypatch, False)
    assert gallery_filters(w.event) == []


def test_an_event_without_stages_offers_no_filters(monkeypatch):
    w = world(monkeypatch)
    search(monkeypatch, True)
    assert gallery_filters(w.event) == []


def test_filter_by_fields_accepts_exactly_the_offered_filters(monkeypatch):
    from apps.events.submissions.gallery_models import GalleryEntry
    w = staged(monkeypatch)
    rows = GalleryEntry.objects.filter(event=w.event)
    assert filter_by_fields(w.event, rows, {}) is rows
    with pytest.raises(ValidationError):
        filter_by_fields(w.event, rows, {"field.budget": "Low"})  # staff-only field
    with pytest.raises(ValidationError):
        filter_by_fields(w.event, rows, {"field.track": "Space"})  # not one of its choices
    with pytest.raises(ValidationError):
        filter_by_fields(w.event, rows, {"field.idea_track": "Health"})  # an earlier stage's field
    assert list(filter_by_fields(w.event, rows, {"field.track": "Health"})) == []


@pytest.mark.parametrize("on", [True, False])
def test_the_gallery_list_carries_the_filters_beside_the_page(monkeypatch, on):
    w = staged(monkeypatch)
    search(monkeypatch, on)
    monkeypatch.setattr(gallery_views, "public_event", lambda **_kwargs: w.event)
    token = uuid4()
    request = APIRequestFactory().get(f"/api/v1/public/event-programmes/{token}/gallery/")
    response = gallery_views.GalleryList.as_view()(request, public_token=token)
    assert response.status_code == 200, response.data
    assert set(response.data) == {"count", "next", "previous", "results", "filters"}
    expected = [{"key": "track", "label": "Track", "choices": ["Health", "Climate"]}] if on else []
    assert response.data["filters"] == expected
