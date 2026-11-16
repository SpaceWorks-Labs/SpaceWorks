"""No partial graph/quota survives provider or final database failure."""

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.audit.models import AuditLog
from apps.evidence.storage import StorageUnavailable
from apps.events import services_clone
from apps.events.models import Event
from apps.events.models_website import EventPage, EventPageAsset
from apps.events.services_clone import duplicate_event
from apps.events.services_website import save_content
from apps.events.website_projection import project
from apps.makerspaces import website_assets
from apps.makerspaces import event_asset_work, website_asset_journal
from apps.makerspaces.limits_usage import _storage
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup as Cleanup
from apps.makerspaces.public_page_asset_cleanup import clean_object
from tests.public_pages.l1c_storage import object_store, upload, inherit
from tests.public_pages.l1b_threads import database_worker

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("failed_stage", ["staging", "final", "staging_delete"])
def test_upload_failure_then_retry_creates_one_asset_and_one_quota_charge(event_owner, object_store, monkeypatch, failed_stage):
    space, actor, event = event_owner
    put, delete = website_assets._put, website_assets.delete_object
    def failed_put(key, data, mime):
        put(key, data, mime)
        if key.startswith("staging/") == (failed_stage == "staging"):
            raise StorageUnavailable("timeout after write")
    def failed_delete(key):
        if key.startswith("staging/"):
            # Only fail the transient delete; the compensating cleaner will retry.
            monkeypatch.setattr(website_assets, "delete_object", delete)
            raise StorageUnavailable("delete timeout")
        return delete(key)
    if failed_stage == "staging_delete":
        monkeypatch.setattr(website_assets, "delete_object", failed_delete)
    else:
        monkeypatch.setattr(website_assets, "_put", failed_put)
    with pytest.raises(StorageUnavailable):
        upload(event, actor)
    assert not EventPage.objects.filter(event=event).exists()
    assert not object_store.private and Cleanup.objects.get().completed_at
    space.refresh_from_db()
    assert _storage(space) == 0
    assert not AuditLog.objects.filter(action="event.website_asset_saved").exists()
    monkeypatch.setattr(website_assets, "_put", put)
    result = upload(event, actor)
    space.refresh_from_db()
    assert space.storage_bytes_used == result.size_bytes
    assert EventPageAsset.objects.count() == 1
    assert set(object_store.private) == {result.object_key}
    assert AuditLog.objects.filter(action="event.website_asset_saved").count() == 1


def test_copy_timeout_and_failed_cleanup_remain_debt_across_successful_retry(event_owner, object_store, monkeypatch):
    space, actor, event = event_owner
    source = upload(event, actor)
    copy, delete = website_assets.copy_object, website_assets.delete_object
    def timed_out(src, dst):
        copy(src, dst)
        raise StorageUnavailable("copy may have succeeded")
    monkeypatch.setattr(website_assets, "copy_object", timed_out)
    monkeypatch.setattr(website_assets, "delete_object", lambda key: False)
    with pytest.raises(StorageUnavailable):
        duplicate_event(event, actor=actor)
    debt = Cleanup.objects.exclude(object_key=source.object_key).get()
    assert debt.attempts == 1 and not debt.storage_accounted and not debt.completed_at
    assert Event.objects.count() == EventPageAsset.objects.count() == 1
    space.refresh_from_db()
    assert _storage(space) == source.size_bytes * 2
    monkeypatch.setattr(website_assets, "copy_object", copy)
    monkeypatch.setattr(website_assets, "delete_object", delete)
    clone = duplicate_event(event, actor=actor)
    space.refresh_from_db()
    assert space.storage_bytes_used == source.size_bytes * 2
    assert _storage(space) == source.size_bytes * 3
    Cleanup.objects.filter(pk=debt.pk).update(due_at=timezone.now())
    assert clean_object(debt.pk)
    space.refresh_from_db()
    assert space.storage_bytes_used == _storage(space) == source.size_bytes * 2
    assert set(object_store.private) == {source.object_key, clone.website_page.assets.get().object_key}


def test_final_database_failure_cleans_private_and_public_copies_atomically(event_owner, object_store, monkeypatch):
    space, actor, event = event_owner
    source = upload(event, actor)
    event.image_key = f"event/{space.pk}/cover.png"
    event.save(update_fields=["image_key"])
    object_store.public[event.image_key] = b"cover"
    def fail(*args, **kwargs):
        raise RuntimeError("audit failure")
    monkeypatch.setattr(services_clone, "_audit", fail)
    with pytest.raises(RuntimeError, match="audit failure"):
        duplicate_event(event, actor=actor)
    assert any(verb == "copy" for _, verb, _ in object_store.calls)
    assert Event.objects.count() == EventPage.objects.count() == EventPageAsset.objects.count() == 1
    assert set(object_store.private) == {source.object_key}
    assert set(object_store.public) == {event.image_key}
    assert not AuditLog.objects.filter(action="event.duplicated").exists()
    space.refresh_from_db()
    assert _storage(space) == space.storage_bytes_used == source.size_bytes
    assert Cleanup.objects.exclude(object_key=source.object_key).filter(completed_at__isnull=True).count() == 0


@pytest.mark.parametrize("mutation", ["clone_source", "cow_template"])
def test_source_edit_during_storage_is_preserved_and_aborts_whole_operation(event_owner, object_store, mutation):
    space, actor, event = event_owner
    target = inherit(event) if mutation == "cow_template" else event
    source = upload(target, actor)
    original = project(target)
    def change(bucket, verb, key):
        if verb != "copy":
            return
        object_store.hook = None
        def save():
            data = project(target)
            data["tagline"] = "Concurrent editor wins"
            save_content(target, actor=actor, data=data)
        with database_worker(save) as (future, _):
            future.result(timeout=10)
    object_store.hook = change
    with pytest.raises(ValidationError) as failure:
        if mutation == "clone_source":
            duplicate_event(event, actor=actor)
        else:
            save_content(event, actor=actor, data={"revision": original["revision"], "sections": [], "sessions": []})
    assert "revision" in failure.value.detail
    assert project(target)["tagline"] == "Concurrent editor wins"
    assert Event.objects.count() == 1 and EventPage.objects.count() == 1
    assert set(object_store.private) == {source.object_key}
    space.refresh_from_db()
    assert _storage(space) == source.size_bytes


def test_replayed_object_work_and_receipt_finalize_do_not_recopy_or_recharge(event_owner, object_store, monkeypatch):
    space, actor, event = event_owner
    source = upload(event, actor)
    perform, finalize = event_asset_work.perform, website_asset_journal.finalize
    def replay_work(plan):
        perform(plan)
        perform(plan)
    def replay_finalize(plan):
        finalize(plan)
        finalize(plan)
    monkeypatch.setattr(event_asset_work, "perform", replay_work)
    monkeypatch.setattr(website_asset_journal, "finalize", replay_finalize)
    object_store.calls.clear()
    clone = duplicate_event(event, actor=actor)
    assert sum(verb == "copy" for _, verb, _ in object_store.calls) == 1
    space.refresh_from_db()
    assert space.storage_bytes_used == source.size_bytes + clone.website_page.assets.get().size_bytes
    assert AuditLog.objects.filter(action="event.duplicated").count() == 1


def test_cleaner_claim_fences_late_upload_and_quota_is_never_credited_twice(event_owner, object_store):
    space, actor, event = event_owner
    def expire(bucket, verb, key):
        if verb != "put" or key.startswith("staging/"):
            return
        object_store.hook = None
        job = Cleanup.objects.get(object_key=key)
        Cleanup.objects.filter(pk=job.pk).update(due_at=timezone.now())
        assert clean_object(job.pk)
        # The interrupted PUT proceeds after this hook: it is a late write to an
        # already cleaned claim. Finalize must refuse, and cleanup repairs it.
    object_store.hook = expire
    with pytest.raises(ValidationError):
        upload(event, actor)
    job = Cleanup.objects.get()
    assert job.attempts == 2 and job.completed_at and not job.storage_accounted
    assert not object_store.private and not EventPageAsset.objects.exists()
    space.refresh_from_db()
    assert _storage(space) == space.storage_bytes_used == 0


def test_freeze_during_storage_waits_for_the_prepared_write_boundary(event_owner, object_store):
    """Decision #86: the events-programme preparation holds the tenant write boundary
    across the reserve/replay storage pass, so a source freeze requested mid-upload
    waits for the write instead of interleaving with it; the journal still charges
    the attached object exactly once and leaves no cleanup debt."""
    from contextlib import ExitStack
    from apps.tenant_migration.source_gate import claim, reopen_after_verified_abort
    from tests.public_pages.l1b_threads import wait_for_blocked
    from tests.tenant_migration.source_gate_helpers import make_actor
    space, actor, event = event_owner
    platform = make_actor("l1c-freeze")
    stack, pending = ExitStack(), {}
    def freeze(bucket, verb, key):
        if verb != "put" or key.startswith("staging/"):
            return
        object_store.hook = None
        pending["claim"], pid = stack.enter_context(database_worker(lambda: claim(space, platform)))
        wait_for_blocked(pid)
        assert not pending["claim"].done()
    object_store.hook = freeze
    with stack:
        asset = upload(event, actor)
        pending["claim"].result(timeout=10)
    job = Cleanup.objects.get(object_key=asset.object_key)
    assert job.storage_accounted and EventPageAsset.objects.filter(pk=asset.pk).exists()
    space.refresh_from_db()
    assert space.storage_bytes_used == asset.size_bytes == _storage(space)
    reopen_after_verified_abort(space, platform)


def test_quota_tightened_after_reservation_refuses_finalize(event_owner, object_store, monkeypatch):
    from apps.makerspaces import limits
    space, actor, event = event_owner
    def tighten(bucket, verb, key):
        if verb == "put":
            monkeypatch.setattr(limits, "resource_limit", lambda *args: 1)
    object_store.hook = tighten
    with pytest.raises(ValidationError):
        upload(event, actor)
    assert not object_store.private and not EventPage.objects.exists()
    space.refresh_from_db()
    assert _storage(space) == space.storage_bytes_used == 0


def test_finalizer_reads_current_owner_quota_overrides(event_owner, object_store, monkeypatch):
    from apps.makerspaces import limits
    from apps.makerspaces.limits_core import resource_limit
    from apps.makerspaces.models import Makerspace
    space, actor, event = event_owner
    monkeypatch.setattr(limits, "resource_limit", resource_limit)
    Makerspace.objects.filter(pk=space.pk).update(resource_limit_overrides={"storage": 100_000})
    def tighten(bucket, verb, key):
        if verb != "put":
            return
        object_store.hook = None
        with database_worker(lambda: Makerspace.objects.filter(pk=space.pk).update(
                resource_limit_overrides={"storage": 1})) as (future, _):
            future.result(timeout=10)
    object_store.hook = tighten
    with pytest.raises(ValidationError):
        upload(event, actor)
    assert not object_store.private and not EventPage.objects.exists()
    space.refresh_from_db()
    assert _storage(space) == space.storage_bytes_used == 0
