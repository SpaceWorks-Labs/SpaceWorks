"""Storage observes autocommit and a second connection can take domain locks."""

from threading import Event as Signal
import pytest
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.events.models import Event, EventSeries
from apps.events.models_website import EventPage, EventPageAsset
from apps.events.services_clone import duplicate_event
from apps.events.services_website import save_content
from apps.events.website_projection import project
from apps.makerspaces import limits, website_assets
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup as Cleanup
from tests.events.website_helpers import section
from tests.public_pages.l1b_threads import database_worker
from tests.public_pages.l1c_storage import object_store, upload, inherit
from tests.public_pages.test_l1_assets import picture

pytestmark = pytest.mark.django_db(transaction=True)


def available_locks(space, actor, event):
    """NOWAIT makes accidentally retained locks fail immediately, rather than hang."""
    with transaction.atomic():
        if event.series_id:
            EventSeries.objects.select_for_update(nowait=True).get(pk=event.series_id)
        Event.objects.select_for_update(nowait=True).get(pk=event.pk)
        Makerspace.objects.select_for_update(nowait=True).get(pk=space.pk)
        User.objects.select_for_update(nowait=True).get(pk=actor.pk)
        list(MakerspaceMembership.staff_tracks.select_for_update(nowait=True).filter(user=actor, makerspace=space))
        list(EventPage.objects.select_for_update(nowait=True).filter(makerspace=space))


@pytest.mark.parametrize("operation", ["upload", "clone", "cow_save", "cow_upload"])
def test_all_storage_calls_are_outside_atomic_and_domain_locks_are_released(event_owner, object_store, operation):
    space, actor, event = event_owner
    if operation.startswith("cow"):
        template = inherit(event)
        source = upload(template, actor)
    elif operation == "clone":
        source = upload(event, actor)
        event.image_key = f"event/{space.pk}/source.png"
        event.save(update_fields=["image_key"])
        object_store.public[event.image_key] = b"public image"
    before_events, before_pages = Event.objects.count(), EventPage.objects.count()
    before_assets = EventPageAsset.objects.count()
    observed = []
    def probe(bucket, verb, key):
        # This runs for HEAD/PUT/COPY/DELETE, including public covers and staging.
        def inspect():
            available_locks(space, actor, event)
            assert Event.objects.count() == before_events
            assert EventPage.objects.count() == before_pages
            assert EventPageAsset.objects.count() == before_assets
        with database_worker(inspect) as (future, _):
            future.result(timeout=10)
        observed.append(verb)
    object_store.hook = probe
    if operation == "clone":
        result = duplicate_event(event, actor=actor)
        assert not result.website_page.released
        assert len(object_store.public) == 2
    elif operation == "cow_save":
        save_content(event, actor=actor, data={"revision": project(event)["revision"],
            "sections": [section(asset_id=source.pk)], "sessions": []})
    else:
        upload(event, actor)
    assert observed
    assert EventPageAsset.objects.count() > before_assets
    space.refresh_from_db()
    # Source cover bytes were installed by the test, not charged by an upload.
    newly_copied_cover = len(b"public image") if operation == "clone" else 0
    assert space.storage_bytes_used == sum(map(len, object_store.private.values())) + newly_copied_cover
    assert AuditLog.objects.filter(action="event.duplicated" if operation == "clone" else
        "event.website_saved" if operation == "cow_save" else "event.website_asset_saved").exists()


def test_pending_quota_reservation_blocks_second_writer_during_storage(event_owner, object_store, monkeypatch):
    space, actor, event = event_owner
    size = len(website_assets.webp(picture().read()))
    monkeypatch.setattr(limits, "resource_limit", lambda *args: size)
    entered, release = Signal(), Signal()
    def pause(bucket, verb, key):
        if verb == "put" and not key.startswith("staging/"):
            entered.set()
            assert release.wait(10)
    object_store.hook = pause
    with database_worker(lambda: upload(event, actor)) as (future, _):
        try:
            assert entered.wait(5)
            assert not EventPage.objects.filter(event=event).exists()
            assert Cleanup.objects.filter(storage_accounted=False, completed_at__isnull=True).count() == 1
            with pytest.raises(ValidationError):
                upload(event, actor)
        finally:
            release.set()
        asset = future.result(timeout=15)
    space.refresh_from_db()
    assert space.storage_bytes_used == size == asset.size_bytes
    assert EventPageAsset.objects.count() == Cleanup.objects.count() == 1


def test_authority_revocation_commits_during_storage_and_finalizer_refuses(event_owner, object_store):
    space, actor, event = event_owner
    def revoke(bucket, verb, key):
        if verb != "put" or key.startswith("staging/"):
            return
        object_store.hook = None
        def change():
            with transaction.atomic():
                available_locks(space, actor, event)
                member = MakerspaceMembership.staff_tracks.select_for_update().get(makerspace=space, user=actor)
                member.status = "revoked"
                member.save(update_fields=["status"])
        with database_worker(change) as (future, _):
            future.result(timeout=10)
    object_store.hook = revoke
    with pytest.raises(PermissionDenied):
        upload(event, actor)
    assert not EventPage.objects.filter(event=event).exists()
    assert not object_store.private
    assert Cleanup.objects.get().completed_at
    space.refresh_from_db()
    assert space.storage_bytes_used == 0


def test_nested_service_transaction_is_refused_before_storage(event_owner, object_store):
    _, actor, event = event_owner
    with transaction.atomic(), pytest.raises(RuntimeError):
        upload(event, actor)
    assert not object_store.calls and not Cleanup.objects.exists()
