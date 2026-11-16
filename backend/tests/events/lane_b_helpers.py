"""Real storage adapter boundary with an in-memory object store for bounded copy tests."""

from unittest.mock import Mock

from apps.inventory import public_image_storage
from apps.makerspaces import limits


def fake_storage(monkeypatch, space, source_key=None, *, size=123):
    source_key = source_key or f"event/{space.pk}/source.png"
    objects = {source_key: size}

    def copy(source, target):
        objects[target] = objects[source]

    def delete(key):
        objects.pop(key, None)
        return True

    copy_mock, delete_mock = Mock(side_effect=copy), Mock(side_effect=delete)
    monkeypatch.setattr(public_image_storage, "object_size", lambda key: objects.get(key))
    monkeypatch.setattr(public_image_storage, "copy_object", copy_mock)
    monkeypatch.setattr(public_image_storage, "delete_object", delete_mock)
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    monkeypatch.setattr(limits, "resource_limit", lambda *args: 100_000)
    return source_key, objects, copy_mock, delete_mock
