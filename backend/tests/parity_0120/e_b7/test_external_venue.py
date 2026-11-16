"""Decision 295: external venue address and https map link on events."""
import pytest
from django.core.exceptions import ValidationError

from apps.events.online_delivery import map_url
from apps.events.venue import validate_map_url
from tests.events.collab_helpers import make_event, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("value", ["http://maps.example.test/x", "javascript:alert(1)", "https://u:p@maps.example.test/",
                                   "https://maps.example.test/a b", "ftp://maps.example.test/"])
def test_map_links_must_be_plain_https(value):
    with pytest.raises(ValidationError):
        validate_map_url(value)


def test_valid_and_blank_links_pass():
    validate_map_url("")
    validate_map_url("https://maps.example.test/place?q=hall")


def test_map_url_prefers_the_venue_link_then_the_space():
    space = make_space("venue-a")
    space.map_url = "https://space.example.test/map"
    space.save(update_fields=["map_url"])
    event = make_event(space)
    assert map_url(event) == "https://space.example.test/map"
    event.venue_map_url = "https://venue.example.test/hall"
    assert map_url(event) == "https://venue.example.test/hall"


def test_full_clean_rejects_a_bad_map_link_and_long_address():
    event = make_event(make_space("venue-b"))
    event.venue_map_url = "http://insecure.example.test"
    with pytest.raises(ValidationError):
        event.full_clean(validate_unique=False, validate_constraints=False)
    event.venue_map_url = ""
    event.venue_address = "x" * 501
    with pytest.raises(ValidationError):
        event.full_clean(validate_unique=False, validate_constraints=False)
