"""Observable object boundaries shared by the event locking/failure tests."""

from types import SimpleNamespace
import pytest
from django.db import connection
from apps.inventory import public_image_storage
from apps.makerspaces import limits, website_assets
from tests.public_pages.test_l1_assets import picture


@pytest.fixture
def object_store(monkeypatch):
    state = SimpleNamespace(private={}, public={}, calls=[], hook=None)
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    monkeypatch.setattr(limits, "resource_limit", lambda *args: 100_000)
    def observe(bucket, verb, key):
        assert not connection.in_atomic_block, (bucket, verb, key)
        state.calls.append((bucket, verb, key))
        if state.hook:
            state.hook(bucket, verb, key)
    for name, module in (("private", website_assets), ("public", public_image_storage)):
        objects = getattr(state, name)
        def size(key, objects=objects, name=name):
            observe(name, "head", key)
            return len(objects[key]) if key in objects else None
        def copy(src, dst, objects=objects, name=name):
            observe(name, "copy", dst)
            objects[dst] = objects[src]
        def delete(key, objects=objects, name=name):
            observe(name, "delete", key)
            objects.pop(key, None)
            return True
        monkeypatch.setattr(module, "object_size", size)
        monkeypatch.setattr(module, "copy_object", copy)
        monkeypatch.setattr(module, "delete_object", delete)
    def put(key, data, mime):
        observe("private", "put", key)
        state.private[key] = data
    monkeypatch.setattr(website_assets, "_put", put)
    return state


def upload(target, actor, **kwargs):
    from apps.events.services_website_assets import upload_asset
    return upload_asset(target, actor=actor, file=picture(), alt_text="Workbench", **kwargs)


def inherit(event):
    from apps.events.models import EventSeries
    start = event.starts_at
    series = EventSeries.objects.create(makerspace=event.makerspace, title="Series",
        recurrence_timezone="UTC", dtstart_local_date=start.date(),
        dtstart_local_time=start.time().replace(tzinfo=None),
        recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=120, status="published")
    event.series, event.series_revision, event.series_occurrence_key = series, 1, "first"
    event.save(update_fields=["series", "series_revision", "series_occurrence_key"])
    return series
