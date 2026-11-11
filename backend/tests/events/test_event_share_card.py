"""L1 G5: the per-event share image and share meta."""

import pytest
from rest_framework.test import APIClient

from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)


def image(event):
    return APIClient().get(f"/api/v1/public/{event.makerspace.slug}/events/{event.public_token}/share.png")


def test_share_png_renders_for_a_public_event():
    event = open_event(event_space("sharing"), location="Main hall")
    response = image(event)
    assert response.status_code == 200 and response["Content-Type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    from io import BytesIO
    from PIL import Image
    assert Image.open(BytesIO(response.content)).size == (1200, 630)
    assert "X-Robots-Tag" not in response


def test_share_png_for_unlisted_is_noindex_and_offline_or_private_is_404():
    event = open_event(event_space("sharing2"), listing="unlisted")
    assert image(event)["X-Robots-Tag"] == "noindex, nofollow"
    event.page_state = "offline"
    event.save(update_fields=["page_state"])
    assert image(event).status_code == 404
    event.page_state, event.is_public = "live", False
    event.save(update_fields=["page_state", "is_public"])
    assert image(event).status_code == 404


def test_cover_less_share_meta_points_at_the_rendered_image(settings):
    settings.PUBLIC_APP_BASE_URL = "https://testserver"
    event = open_event(event_space("sharing3"))
    html = APIClient().get(f"/share/e/{event.public_token}/").content.decode()
    assert f"/events/{event.public_token}/share.png" in html and 'og:image' in html


def test_share_png_is_cached_per_revision():
    from apps.events.share_cards import revision
    event = open_event(event_space("sharing4"))
    before = revision(event)
    event.title = "Renamed"
    assert revision(event) != before
