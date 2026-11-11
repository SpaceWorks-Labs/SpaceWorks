"""Purge and clone keep byte ownership and publication boundaries separate."""

import pytest
from django.utils import timezone

from apps.events.models_website import EventPage, EventPageAsset
from apps.events.services_website import save_content, set_release
from apps.makerspaces import public_page_services as pages
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup
from apps.makerspaces.public_page_contract import empty_document
from tests.events.website_helpers import session

pytestmark = pytest.mark.django_db(transaction=True)


def saved(event_owner):
    space, actor, event = event_owner
    save_content(event, actor=actor, data={"revision": 0, "sections": [], "sessions": [session(event)]})
    return space, actor, event, EventPage.objects.get(event=event)


def test_event_module_purge_journals_private_bytes_and_retains_other_pages(event_owner, monkeypatch, settings):
    from apps.accounts.models import User
    from apps.makerspaces.module_purge import purge_module
    from apps.makerspaces.models_public_pages import MakerspacePublicPage
    from apps.makerspaces.public_page_asset_cleanup import clean_object
    from apps.organizations.models import Organization
    from apps.organizations.models_public_pages import OrganizationPublicPage
    space, actor, event, page = saved(event_owner)
    pages.save("makerspace", space.pk, actor=actor, version=0, document=empty_document("makerspace"))
    organization = Organization.objects.create(name="Unrelated global", slug="purge-global")
    global_page = OrganizationPublicPage.objects.create(organization=organization)
    key = f"events/website/{space.pk}/{page.pk}/owned.webp"
    EventPageAsset.objects.create(page=page, object_key=key, size_bytes=5, alt_text="Programme cover")
    space.enabled_modules = [name for name in space.enabled_modules if name != "events"]
    space.save(update_fields=["enabled_modules"])
    settings.MANAGED_POSTGRES = True
    monkeypatch.setattr("apps.makerspaces.module_purge._delete_private_keys", lambda _: set())
    root = User.objects.create_superuser(username="page-purge-root", password=None)
    # ORM purge runs cleanup on commit too. Fail that first attempt deliberately
    # so the assertions below exercise the durable retry, without live storage.
    with monkeypatch.context() as purge_storage:
        purge_storage.setattr("apps.makerspaces.website_assets.delete_object", lambda _: False)
        purge_module(space, "events", root)
    assert not EventPage.objects.filter(pk=page.pk).exists()
    assert MakerspacePublicPage.objects.filter(makerspace=space).exists()
    assert OrganizationPublicPage.objects.filter(pk=global_page.pk).exists()
    job = PublicPageObjectCleanup.objects.get(object_key=key)
    assert job.owner_kind == "event" and job.ownership_proven and job.storage_accounted
    assert job.attempts == 1 and job.completed_at is None
    PublicPageObjectCleanup.objects.filter(pk=job.pk).update(due_at=timezone.now())
    deleted, freed = [], []
    monkeypatch.setattr("apps.makerspaces.website_assets.delete_object", lambda value: deleted.append(value) or True)
    monkeypatch.setattr("apps.makerspaces.limits.free_storage", lambda owner, size: freed.append((owner.pk, size)))
    assert clean_object(job.pk)
    assert deleted == ["staging/" + key, key] and freed == [(space.pk, 5)]
    assert not clean_object(job.pk)


def test_clone_has_fresh_snapshot_identities_and_no_publication(event_owner):
    from apps.events.services_clone import duplicate_event
    space, actor, event, page = saved(event_owner)
    set_release(event, actor=actor, released=True, revision=page.revision)
    page.refresh_from_db()
    clone = duplicate_event(event, actor=actor)
    target = EventPage.objects.get(event=clone)
    assert target.makerspace_id == space.pk
    assert target.draft_revision_id and target.draft_revision_id != page.draft_revision_id
    assert target.published_revision_id is None and not target.released
    assert not set(target.session_identities.values_list("pk", flat=True)) & set(page.session_identities.values_list("pk", flat=True))
    assert target.session_aliases.get(slug="talk").identity_id != page.session_aliases.get(slug="talk").identity_id


def test_successful_module_purge_does_not_release_page_storage_twice(event_owner, monkeypatch, settings):
    from apps.accounts.models import User
    from apps.makerspaces.module_purge import purge_module
    space, _, _, page = saved(event_owner)
    key = f"events/website/{space.pk}/{page.pk}/once.webp"
    EventPageAsset.objects.create(page=page, object_key=key, size_bytes=5, alt_text="Cover")
    space.enabled_modules = [name for name in space.enabled_modules if name != "events"]
    space.save(update_fields=["enabled_modules"])
    settings.MANAGED_POSTGRES = True
    deleted, freed = [], []
    monkeypatch.setattr("apps.makerspaces.website_assets.delete_object", lambda value: deleted.append(value) or True)
    monkeypatch.setattr("apps.makerspaces.limits.free_storage", lambda owner, size: freed.append((owner.pk, size)))
    # The legacy collector confirms the same final key after on_commit cleanup.
    monkeypatch.setattr("apps.makerspaces.module_purge._delete_private_keys", lambda keys: set(keys))
    root = User.objects.create_superuser(username="page-purge-once", password=None)
    purge_module(space, "events", root)
    job = PublicPageObjectCleanup.objects.get(object_key=key)
    assert job.completed_at and job.storage_accounted
    assert deleted == ["staging/" + key, key]
    assert freed == [(space.pk, 5)]


def test_raw_event_purge_keeps_imported_key_ownership_for_cleanup(event_owner, monkeypatch):
    from datetime import timedelta
    from apps.makerspaces.public_page_asset_cleanup import clean_object
    from apps.makerspaces.public_page_lifecycle import enqueue_tenant_pages
    from apps.tenant_migration.models_import_job import TenantImportJob
    from apps.tenant_migration.models_import_objects import TenantImportObject
    space, _, _, page = saved(event_owner)
    imported = TenantImportJob.objects.create(target_makerspace=space,
        expires_at=timezone.now() + timedelta(days=1))
    key = f"migrated-objects/{imported.pk}/owned.webp"
    object_row = TenantImportObject.objects.create(job=imported, bucket_kind="private",
        source_key="events/website/100/200/old.webp", target_key=key,
        staging_key=f"tenant-imports/{imported.pk}/staging", size=5, sha256="a" * 64, state="verified")
    asset = EventPageAsset.objects.create(page=page, object_key=key, size_bytes=5, alt_text="Imported")
    enqueue_tenant_pages(space, events_only=True)
    job = PublicPageObjectCleanup.objects.get(object_key=key)
    assert job.owner_kind == "event" and job.ownership_proven and job.storage_accounted
    # Raw lifecycle deletion must work without the ORM receiver or import journal.
    EventPageAsset.objects.filter(pk=asset.pk)._raw_delete("default")
    object_row.delete()
    deleted, freed = [], []
    monkeypatch.setattr("apps.makerspaces.website_assets.delete_object", lambda value: deleted.append(value) or True)
    monkeypatch.setattr("apps.makerspaces.limits.free_storage", lambda owner, size: freed.append((owner.pk, size)))
    assert clean_object(job.pk)
    assert deleted == ["staging/" + key, key] and freed == [(space.pk, 5)]


def test_failed_cleanup_retains_charge_and_retries(event_owner, monkeypatch):
    from apps.makerspaces.public_page_asset_cleanup import clean_object
    from apps.makerspaces.public_page_lifecycle import enqueue_tenant_pages
    from django.db import connection, transaction
    space, _, _, page = saved(event_owner)
    key = f"events/website/{space.pk}/{page.pk}/retry.webp"
    EventPageAsset.objects.create(page=page, object_key=key, size_bytes=10, alt_text="Retry")
    def outage(_):
        raise RuntimeError("storage unavailable")
    # Asset deletion schedules cleanup on commit. Install the failure before
    # that callback runs so the test actually exercises outstanding byte debt.
    monkeypatch.setattr("apps.makerspaces.website_assets.delete_object", outage)
    monkeypatch.setattr("apps.makerspaces.limits.free_storage", lambda *_: pytest.fail("Unconfirmed deletion freed quota"))
    with transaction.atomic():
        enqueue_tenant_pages(space, events_only=True)
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        page.delete()
    job = PublicPageObjectCleanup.objects.get(object_key=key)
    assert not clean_object(job.pk)
    job.refresh_from_db()
    assert job.attempts == 1 and job.completed_at is None


def test_global_editor_does_not_inherit_frozen_linked_tenant(page_owner):
    from apps.makerspaces.origin_scope_routes import authoritative_route_resolution
    from apps.tenant_migration.gate_runtime import assert_request_write_allowed
    from django.urls import resolve
    from rest_framework.test import APIRequestFactory
    from apps.tenant_migration.source_gate import claim
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    space, actor = page_owner
    claim(space, actor)
    with pytest.raises(SourceMigrationGateClosed):
        assert_write_allowed(space.pk)
    request = APIRequestFactory().put("/api/v1/admin/organizations/1/public-page/", {})
    request.resolver_match = resolve(request.path)
    request.selected_makerspace_id = page_owner[0].pk
    assert authoritative_route_resolution(request) == (set(), True)
    assert_request_write_allowed(request)
