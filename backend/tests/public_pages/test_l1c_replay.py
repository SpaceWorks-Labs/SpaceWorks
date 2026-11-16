"""Final graph replay preserves COW identities and refuses stale image inputs."""

from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.audit.models import AuditLog
from apps.events.models_website import EventPage, EventPageAsset
from apps.events.services_clone import duplicate_event
from apps.events.services_website import save_content, set_release
from apps.events.website_projection import project
from apps.makerspaces import event_asset_work
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup as Cleanup
from apps.makerspaces.public_page_asset_cleanup import clean_object
from tests.events.website_helpers import section, session
from tests.public_pages.l1c_storage import object_store, upload, inherit

pytestmark = pytest.mark.django_db(transaction=True)


def test_cow_replace_remaps_inherited_asset_and_keeps_template_publication(event_owner, object_store):
    _, actor, event = event_owner
    series = inherit(event)
    source = upload(series, actor)
    save_content(series, actor=actor, data={"revision": project(series)["revision"],
        "sections": [section(asset_id=source.pk)], "sessions": []})
    set_release(series, actor=actor, released=True, revision=project(series)["revision"])
    template = EventPage.objects.get(series=series)
    publication = template.published_revision_id
    replacement = upload(event, actor, replace_id=source.pk, revision=project(event)["revision"])
    override = EventPage.objects.get(event=event)
    assert not override.released and override.published_revision_id is None
    assert override.sections.get().asset_id == replacement.pk
    assert override.assets.count() == 2  # copied history plus fresh replacement
    template.refresh_from_db()
    assert template.released and template.published_revision_id == publication
    assert template.sections.get().asset_id == source.pk
    assert len(object_store.private) == 3


def test_cow_session_and_asset_identity_maps_are_from_the_final_pass(event_owner, object_store):
    space, actor, event = event_owner
    series = inherit(event)
    source = upload(series, actor)
    save_content(series, actor=actor, data={"revision": project(series)["revision"],
        "sections": [section("speaker", "speaker", asset_id=source.pk)],
        "sessions": [session(event, speakers=["speaker"])]})
    inherited = project(event)
    prior_identity = inherited["sessions"][0]["session_id"]
    save_content(event, actor=actor, data=inherited)
    current = project(event)
    assert not current["inherited"] and not current["released"]
    assert current["sessions"][0]["session_id"] != prior_identity
    own = EventPage.objects.get(event=event)
    speaker = own.sessions.get().speaker_links.get().speaker
    assert speaker.page_id == own.pk and speaker.asset_id != source.pk
    assert own.draft_revision.asset_references.get().asset_id == speaker.asset_id
    assert own.session_aliases.get().identity_id == own.sessions.get().identity_id
    assert AuditLog.objects.filter(action="event.website_saved", target_id=str(own.pk)).count() == 1
    space.refresh_from_db()
    assert space.storage_bytes_used == sum(map(len, object_store.private.values()))


def test_stale_upload_precondition_rejects_before_reserving_or_reading_bytes(event_owner, object_store):
    _, actor, event = event_owner
    upload(event, actor)
    jobs = Cleanup.objects.count()
    object_store.calls.clear()
    with pytest.raises(ValidationError) as failure:
        upload(event, actor, revision=0)
    assert "revision" in failure.value.detail
    assert not object_store.calls and Cleanup.objects.count() == jobs


def test_private_source_size_mismatch_refuses_copy_and_compensates(event_owner, object_store):
    space, actor, event = event_owner
    source = upload(event, actor)
    object_store.private[source.object_key] = b"wrong size"
    with pytest.raises(ValidationError):
        duplicate_event(event, actor=actor)
    assert EventPageAsset.objects.count() == 1
    assert set(object_store.private) == {source.object_key}
    space.refresh_from_db()
    assert space.storage_bytes_used == source.size_bytes


def test_upload_object_replay_does_not_replace_verified_final_key(event_owner, object_store, monkeypatch):
    space, actor, event = event_owner
    perform = event_asset_work.perform
    def replay(plan):
        perform(plan)
        perform(plan)
    monkeypatch.setattr(event_asset_work, "perform", replay)
    result = upload(event, actor)
    assert sum(verb == "put" and not key.startswith("staging/")
        for _, verb, key in object_store.calls) == 1
    space.refresh_from_db()
    assert space.storage_bytes_used == result.size_bytes


def test_completed_cover_receipt_does_not_credit_legacy_quota_release_twice(event_owner, object_store):
    from apps.inventory import public_image_storage
    space, actor, event = event_owner
    event.image_key = f"event/{space.pk}/source.png"
    event.save(update_fields=["image_key"])
    object_store.public[event.image_key] = b"cover"
    clone = duplicate_event(event, actor=actor)
    job = Cleanup.objects.get(object_key=clone.image_key)
    assert job.completed_at and not job.storage_accounted
    # Legacy artwork release remains the sole counter owner after attachment.
    public_image_storage.release_public_image(space, clone.image_key)
    clone.image_key = ""
    clone.save(update_fields=["image_key"])
    Cleanup.objects.filter(pk=job.pk).update(due_at=timezone.now() - timedelta(seconds=1))
    assert not clean_object(job.pk)
    space.refresh_from_db()
    assert space.storage_bytes_used == 0


def test_live_cover_receipts_cannot_starve_pending_cleanup_jobs(event_owner, object_store):
    from apps.makerspaces.public_page_asset_cleanup import sweep
    space, actor, event = event_owner
    event.image_key = f"event/{space.pk}/source.png"
    event.save(update_fields=["image_key"])
    object_store.public[event.image_key] = b"cover"
    clone = duplicate_event(event, actor=actor)
    Cleanup.objects.filter(object_key=clone.image_key).update(due_at=timezone.now() - timedelta(hours=1))
    key = f"events/website/{space.pk}/98765/orphan.webp"
    orphan = Cleanup.objects.create(owner_kind="event", owner_id=space.pk, page_id=98765,
        object_key=key, size_bytes=4, storage_accounted=False, ownership_proven=True)
    object_store.private[key] = b"webp"
    assert sweep(limit=1)["deleted"] == 1
    orphan.refresh_from_db()
    assert orphan.completed_at and key not in object_store.private
    assert clone.image_key in object_store.public
