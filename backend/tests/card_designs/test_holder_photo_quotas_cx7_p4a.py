"""Member/event holder photos: refuse quotas before final byte writes or consent changes."""
from unittest.mock import Mock

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.card_designs import images, photos
from apps.events.models import Event, EventRegistration
from apps.events.models_id_cards import EventIdCard
from apps.makerspaces import member_card_storage
from apps.makerspaces.models import Makerspace, MemberCard
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.return_helpers import make_member, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_membership, pytest.mark.area_events]
KEYS = [("upload_bytes", 400, "upload_limit"), ("storage", 400, "limit_reached"),
        ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached")]


def world(kind, key, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p4a-holder-photo")
    actor = make_member("p4a-photo-manager", space)
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["resource_limit_overrides"])
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Cards", starts_at=now, ends_at=now + timezone.timedelta(days=1))
    cards = []
    for index in range(2):
        if kind == "member":
            cards.append(MemberCard.objects.create(makerspace=space, card_number=index + 1))
        else:
            registration = EventRegistration.objects.create(event=event, name=f"Holder {index}",
                                                            email=f"holder{index}@example.test", phone="", status="registered")
            cards.append(EventIdCard.objects.create(makerspace=space, event=event, registration=registration,
                                                    valid_until=event.ends_at))
    monkeypatch.setattr(images, "normalise", lambda data, **kw: (data, 1, 1, "#ffffff"))
    monkeypatch.setattr(photos, "normalise", images.normalise)
    put = Mock()
    monkeypatch.setattr(photos, "put_bytes", put)
    monkeypatch.setattr(member_card_storage, "_write_photo", put)
    monkeypatch.setattr(member_card_storage.storage, "validate_evidence_object", lambda key: None)
    monkeypatch.setattr(member_card_storage.storage, "delete_object", lambda key: True)
    return space, actor, cards, put


def attach(kind, actor, card, size, monkeypatch):
    if kind == "event":
        return photos.attach_bytes(actor, "event_card", card, b"x" * size, consent=True)
    monkeypatch.setattr(member_card_storage.storage, "object_size", lambda key: size)
    monkeypatch.setattr(member_card_storage, "_read_upload", lambda key: b"x" * size)
    return member_card_storage.finalize_photo(actor, card,
        object_key=f"member-cards/{card.makerspace_id}/p4a-{card.pk}", content_type="image/png", consent=True)


def snapshot(space, model):
    return (Makerspace.objects.get(pk=space.pk).storage_bytes_used,
            list(model.objects.order_by("pk").values()),
            list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()))


@pytest.mark.parametrize("kind", ["member", "event"])
@pytest.mark.parametrize("key,status,code", KEYS)
def test_holder_photo_max_next_has_no_final_write_metadata_or_consent_change(
        kind, key, status, code, settings, monkeypatch):
    space, actor, cards, put = world(kind, key, settings, monkeypatch)
    attach(kind, actor, cards[0], 10, monkeypatch)
    before = snapshot(space, type(cards[0]))
    put.reset_mock()
    with pytest.raises(APIException) as raised:
        attach(kind, actor, cards[1], 11 if key == "upload_bytes" else 1, monkeypatch)
    assert (raised.value.status_code, str(raised.value.detail["code"])) == (status, code)
    assert snapshot(space, type(cards[0])) == before
    put.assert_not_called()
    assert before[0] == 10


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["member", "event"])
@pytest.mark.parametrize("key,status,code", KEYS[1:])
def test_holder_photo_creators_race_at_last_slot(kind, key, status, code, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, actor, cards, put = world(kind, key, settings, monkeypatch)
    # Both threads read identical external bytes; install the fake before starting them.
    monkeypatch.setattr(member_card_storage.storage, "object_size", lambda key: 10)
    monkeypatch.setattr(member_card_storage, "_read_upload", lambda key: b"x" * 10)
    def create(index):
        if kind == "event":
            photos.attach_bytes(actor, "event_card", cards[index], b"x" * 10, consent=True)
        else:
            member_card_storage.finalize_photo(actor, cards[index],
                object_key=f"member-cards/{space.pk}/p4a-{index}", content_type="image/png", consent=True)
    assert race_creators(create) == [(201, "created"), (status, code)]
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10
    assert type(cards[0]).objects.exclude(photo_object_key="").count() == 1
    assert put.call_count == 1


@pytest.mark.parametrize("kind", ["member", "event"])
def test_holder_presign_full_storage_never_reaches_provider(kind, settings, monkeypatch):
    space, _, cards, _ = world(kind, "storage", settings, monkeypatch)
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=10)
    cards[0].makerspace.refresh_from_db()
    provider = Mock()
    monkeypatch.setattr(photos, "presign_staging", provider)
    monkeypatch.setattr(member_card_storage.storage, "presigned_upload", provider)
    with pytest.raises(APIException) as raised:
        (photos.presign if kind == "event" else member_card_storage.presign_photo)(cards[0], "image/png")
    assert (raised.value.status_code, str(raised.value.detail["code"])) == (400, "upload_limit")
    provider.assert_not_called()


@pytest.mark.parametrize("kind", ["member", "event"])
def test_holder_photo_cannot_hide_oversized_upload_by_shrinking_it(kind, settings, monkeypatch):
    space, actor, cards, provider = world(kind, "upload_bytes", settings, monkeypatch)
    monkeypatch.setattr(images, "normalise", lambda *args, **kw: (b"x", 1, 1, "#ffffff"))
    monkeypatch.setattr(photos, "normalise", images.normalise)
    before = snapshot(space, type(cards[0]))
    with pytest.raises(APIException) as raised:
        attach(kind, actor, cards[0], 11, monkeypatch)
    assert (raised.value.status_code, str(raised.value.detail["code"])) == (400, "upload_limit")
    assert snapshot(space, type(cards[0])) == before
    provider.assert_not_called()


def test_server_generated_photo_replacement_keeps_the_per_file_exemption(settings, monkeypatch):
    space, actor, cards, provider = world("event", "upload_bytes", settings, monkeypatch)
    space.resource_limit_overrides = {"upload_bytes": 0, "storage": 11}
    space.save(update_fields=["resource_limit_overrides"])
    photos.attach_bytes(actor, "event_card", cards[0], b"x" * 11, consent=True, is_upload=False)
    cards[0].refresh_from_db()
    assert cards[0].photo_size_bytes == 11
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 11
    assert provider.call_count == 1
