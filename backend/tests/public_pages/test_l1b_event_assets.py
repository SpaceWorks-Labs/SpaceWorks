"""Crash-safe event bytes, retained revision pins and post-commit owner removal."""
from datetime import timedelta
import pytest
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.evidence.storage import StorageUnavailable
from apps.events.models_website import EventPage, EventPageAsset
from apps.events.services_website import save_content, set_release
from apps.events.services_website_assets import upload_asset, delete_asset
from apps.events.services_clone import duplicate_event
from apps.events.website_projection import project
from apps.events.website_revision_projection import visible_asset_ids
from apps.makerspaces import limits, website_assets
from apps.makerspaces.limits_usage import _storage
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup as Cleanup
from apps.makerspaces.public_page_asset_cleanup import clean_object
from tests.public_pages.test_l1_assets import picture
from tests.events.website_helpers import section

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def store(monkeypatch):
    objects = {}
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    monkeypatch.setattr(limits, "resource_limit", lambda *a: 100_000)
    monkeypatch.setattr(website_assets, "_put", lambda key, value, mime: objects.update({key: value}))
    monkeypatch.setattr(website_assets, "object_size", lambda key: len(objects[key]) if key in objects else None)
    monkeypatch.setattr(website_assets, "copy_object", lambda src, dst: objects.update({dst: objects[src]}))
    def delete(key):
        # Deletion never holds a domain row lock, including rollback cleanup.
        assert not connection.in_atomic_block
        objects.pop(key, None)
        return True
    # Upload removes transient staging while still in its existing clone boundary.
    monkeypatch.setattr(website_assets, "delete_object", lambda key: objects.pop(key, None) is not False
                        if key.startswith("staging/") else delete(key))
    return objects


def upload(event, actor, **kwargs):
    return upload_asset(event, actor=actor, file=picture(), alt_text="Workbench", **kwargs)


def due(job):
    Cleanup.objects.filter(pk=job.pk).update(due_at=timezone.now())


def test_failed_put_and_failed_rollback_delete_leave_durable_quota_debt(event_owner, store, monkeypatch):
    space, actor, event = event_owner
    put = website_assets._put
    def failed_put(key, data, mime):
        put(key, data, mime)
        if not key.startswith("staging/"):
            raise StorageUnavailable()
    monkeypatch.setattr(website_assets, "_put", failed_put)
    delete = website_assets.delete_object
    monkeypatch.setattr(website_assets, "delete_object", lambda key: False)
    with pytest.raises(StorageUnavailable):
        upload(event, actor)
    job = Cleanup.objects.get(owner_kind="event")
    assert job.completed_at is None and job.attempts == 1 and not job.storage_accounted
    assert not EventPageAsset.objects.exists() and not EventPage.objects.filter(event=event).exists()
    space.refresh_from_db()
    assert space.storage_bytes_used == 0 and _storage(space) == job.size_bytes > 0
    monkeypatch.setattr(limits, "resource_limit", lambda *a: job.size_bytes)
    with pytest.raises(ValidationError):
        limits.add_storage(space, 1)
    monkeypatch.setattr(website_assets, "delete_object", delete)
    due(job)
    assert clean_object(job.pk)
    assert not store and _storage(space) == 0
    assert not clean_object(job.pk)
    # Repair a late provider write without subtracting somebody else's quota.
    store[job.object_key] = b"late write"
    due(job)
    assert not clean_object(job.pk)
    assert not store and _storage(space) == 0


def test_failed_clone_copy_keeps_journal_after_page_and_quota_rollback(event_owner, store, monkeypatch):
    space, actor, event = event_owner
    source = upload(event, actor)
    copy = website_assets.copy_object
    def fail(src, dst):
        copy(src, dst)
        raise StorageUnavailable()
    monkeypatch.setattr(website_assets, "copy_object", fail)
    delete = website_assets.delete_object
    monkeypatch.setattr(website_assets, "delete_object", lambda key: False)
    with pytest.raises(StorageUnavailable):
        duplicate_event(event, actor=actor)
    assert event.__class__.objects.filter(makerspace=space).count() == 1
    job = Cleanup.objects.exclude(object_key=source.object_key).get()
    assert not job.storage_accounted and job.completed_at is None
    space.refresh_from_db()
    assert _storage(space) == source.size_bytes + job.size_bytes
    monkeypatch.setattr(website_assets, "delete_object", delete)
    due(job)
    assert clean_object(job.pk)
    assert set(store) == {source.object_key}


def test_replacement_pins_all_saved_versions_but_only_current_public_asset_reads(event_owner, store):
    _, actor, event = event_owner
    first = upload(event, actor)
    save_content(event, actor=actor, data={"revision": project(event)["revision"],
        "sections": [section("portrait", "speaker", asset_id=first.pk)], "sessions": []})
    set_release(event, actor=actor, released=True, revision=project(event)["revision"])
    second = upload(event, actor, replace_id=first.pk)
    page = EventPage.objects.get(event=event)
    assert visible_asset_ids(page.published_revision) == {first.pk}
    assert visible_asset_ids(page.draft_revision) == {second.pk}
    for asset in (first, second):
        with pytest.raises(ValidationError):
            delete_asset(event, asset.pk, actor=actor)
    set_release(event, actor=actor, released=True, revision=page.revision)
    page.refresh_from_db()
    assert visible_asset_ids(page.published_revision) == {second.pk}
    assert set(store) == {first.object_key, second.object_key}


@pytest.mark.parametrize("rollback", [True, False])
def test_whole_owner_delete_only_cleans_after_commit_and_retries(event_owner, store, monkeypatch, rollback):
    space, actor, event = event_owner
    asset = upload(event, actor)
    delete = website_assets.delete_object
    monkeypatch.setattr(website_assets, "delete_object", lambda key: False)
    class Abort(Exception):
        pass
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
            event.delete()
            assert asset.object_key in store
            if rollback:
                raise Abort()
    except Abort:
        pass
    space.refresh_from_db()
    assert space.storage_bytes_used == asset.size_bytes
    if rollback:
        assert EventPageAsset.objects.filter(pk=asset.pk).exists()
        assert Cleanup.objects.get(object_key=asset.object_key).attempts == 0
    else:
        job = Cleanup.objects.get(object_key=asset.object_key)
        assert job.attempts == 1 and job.completed_at is None
        monkeypatch.setattr(website_assets, "delete_object", delete)
        due(job)
        assert clean_object(job.pk)
        space.refresh_from_db()
        assert not store and space.storage_bytes_used == 0


def test_unattached_collector_retains_history_and_checks_age(event_owner, store, monkeypatch):
    from apps.events.website_asset_cleanup import collect_unattached
    _, actor, event = event_owner
    orphan = upload(event, actor)
    retained = upload(event, actor)
    save_content(event, actor=actor, data={"revision": project(event)["revision"],
        "sections": [section(asset_id=retained.pk)], "sessions": []})
    # Asset metadata is immutable: age the clock rather than mutating retained rows.
    later = timezone.now() + timedelta(hours=25)
    monkeypatch.setattr(timezone, "now", lambda: later)
    assert collect_unattached(orphan.page_id) == 1
    assert set(store) == {retained.object_key}


def test_owner_cleanup_retains_import_ownership_proof_after_import_journal_deletion(event_owner, store):
    from apps.tenant_migration.models_import_job import TenantImportJob
    from apps.tenant_migration.models_import_objects import TenantImportObject
    from apps.events.website_asset_cleanup import schedule_page_cleanup
    space, _, event = event_owner
    page = EventPage.objects.create(makerspace=space, event=event)
    imported = TenantImportJob.objects.create(target_makerspace=space, expires_at=timezone.now() + timedelta(days=1))
    key = f"migrated-objects/{imported.pk}/collision.webp"
    TenantImportObject.objects.create(job=imported, bucket_kind="private", source_key="events/website/1/2/image.webp",
        target_key=key, staging_key=f"tenant-imports/{imported.pk}/staging", size=4, sha256="a" * 64, state="verified")
    asset = EventPageAsset.objects.create(page=page, object_key=key, size_bytes=4, alt_text="Imported portrait")
    store[key] = b"webp"
    limits.add_storage(space, 4)
    with transaction.atomic():
        schedule_page_cleanup(page)
        imported.delete()
        asset.delete()
        assert key in store
    job = Cleanup.objects.get(object_key=key)
    assert job.ownership_proven and job.completed_at
    assert key not in store
    space.refresh_from_db()
    assert space.storage_bytes_used == 0
