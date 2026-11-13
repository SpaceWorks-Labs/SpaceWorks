"""D314c fixtures: the provider is always mocked; storage is an in-memory dict; photos are tiny generated PNGs."""
from io import BytesIO

import pytest


def png(size=(40, 60), *, alpha=None, colour=(180, 40, 40)):
    """A PNG. `alpha=None` -> opaque RGB; otherwise an RGBA with that constant alpha."""
    from PIL import Image
    mode = "RGB" if alpha is None else "RGBA"
    image = Image.new(mode, size, colour if alpha is None else (*colour, alpha))
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def cutout_png(size=(40, 60)):
    """Half transparent, half opaque: what a real eraser answers."""
    from PIL import Image
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    image.paste((20, 20, 200, 255), (0, size[1] // 2, size[0], size[1]))
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def jpeg(size=(40, 60)):
    from PIL import Image
    out = BytesIO()
    Image.new("RGB", size, (10, 120, 10)).save(out, format="JPEG")
    return out.getvalue()

PHOTO_FIELDS = ("photo_object_key", "photo_content_type", "photo_size_bytes", "photo_consent_at", "photo_consent_version")


def set_photo(card, key, content_type="image/jpeg"):
    """Give a member card a photo: the DB check constraint makes the five photo columns all-or-nothing."""
    from django.utils import timezone
    card.photo_object_key, card.photo_content_type, card.photo_size_bytes = key, content_type, 1234
    card.photo_consent_at, card.photo_consent_version = timezone.now(), "v1"
    card.save(update_fields=[*PHOTO_FIELDS])


def clear_photo(card):
    card.photo_object_key = card.photo_content_type = card.photo_consent_version = ""
    card.photo_size_bytes = card.photo_consent_at = None
    card.save(update_fields=[*PHOTO_FIELDS])


@pytest.fixture(autouse=True)
def card_test_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}


@pytest.fixture
def store(monkeypatch):
    """In-memory private storage for every module that touches card objects."""
    objects = {}
    from apps.card_designs import cutouts, photo_batch, photo_batch_apply, storage

    def put(key, data, content_type):
        objects[key] = data
        return len(data)

    for module in (cutouts, photo_batch, storage):
        monkeypatch.setattr(module, "put_bytes", put, raising=False)
    for module in (cutouts, photo_batch, photo_batch_apply, storage):
        monkeypatch.setattr(module, "delete_quietly", lambda key: objects.pop(key, None), raising=False)
    monkeypatch.setattr(photo_batch_apply, "get_bytes", lambda key, limit=0: objects.get(key), raising=False)
    monkeypatch.setattr(cutouts, "signed_url", lambda key, **_: f"https://files.test/{key}", raising=False)
    monkeypatch.setattr(photo_batch, "signed_url", lambda key, **_: f"https://files.test/{key}", raising=False)
    monkeypatch.setattr("apps.card_designs.storage.read_optional", lambda key, limit=0: objects.get(key))
    return objects


@pytest.fixture
def original_photo(monkeypatch):
    """Every member card reads as holding this photo."""
    data = jpeg()
    monkeypatch.setattr("apps.makerspaces.member_card_storage.photo_bytes", lambda card: data)
    return data
