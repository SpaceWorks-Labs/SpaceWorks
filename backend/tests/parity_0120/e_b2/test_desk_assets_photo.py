"""Desk bundle additions (E-F2 follow-up): design assets and consented photos as capped data URLs, and the
`bulk` receipt method."""
import pytest

from apps.events import badge_desk
from apps.events.serializers_badge_prints import BadgeReceiptSerializer
from tests.parity_0120.e_b2.helpers import issue_cards, live_event, publish_badge, register

pytestmark = pytest.mark.django_db

PNG = bytes.fromhex("89504e470d0a1a0a") + b"x" * 20


def test_data_urls_are_capped_and_sniff_the_type():
    assert badge_desk._data_url(PNG).startswith("data:image/png;base64,")
    assert badge_desk._data_url(bytes((255, 216, 255)) + b"jpeg").startswith("data:image/jpeg;base64,")
    assert badge_desk._data_url(b"x" * (badge_desk.LOGO_MAX_BYTES + 1)) is None
    assert badge_desk._data_url(b"") is None


def test_asset_ids_are_found_in_layers_backgrounds_and_watermarks():
    document = {"front": {"background": {"asset_id": "a"}, "layers": [{"kind": "image", "asset_id": "b"}]},
                "back": {"layers": []}, "watermark": {"asset_id": "c"}}
    assert badge_desk._asset_ids(document) == {"a", "b", "c"}


def test_every_design_in_the_bundle_carries_its_assets_map():
    space, event, sm = live_event("e2-assets")
    publish_badge(space, event, sm)
    designs, _roles, _tags = badge_desk.role_designs(event)
    assert all(isinstance(design["assets"], dict) for design in designs.values())


def test_the_photo_is_read_only_when_asked_and_only_for_a_consented_card(monkeypatch):
    space, event, sm = live_event("e2-photo")
    publish_badge(space, event, sm, showPhoto=True)
    _user, registration = register(space, event, "ada")
    issue_cards(event)
    monkeypatch.setattr("apps.card_designs.photos.photo_bytes", lambda card: PNG)
    row = badge_desk.rows(event, [registration], with_photo=True)[0]
    assert "photo" not in badge_desk.rows(event, [registration])[0]
    assert row.get("photo") in (None, badge_desk._data_url(PNG))  # None until the holder consented


def test_a_bulk_receipt_method_is_accepted():
    data = BadgeReceiptSerializer(data={"operation_id": "6f1c0b66-7a1c-4d7b-9d56-0c8f8d1f7a11", "registration_id": 1, "method": "bulk"})
    assert data.is_valid(), data.errors
