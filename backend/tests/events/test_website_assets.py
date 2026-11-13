from tests.events.website_helpers import remove_page
from tests.events.website_helpers import make_page
from copy import deepcopy
from datetime import timedelta, time
from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.events.models import EventSeries, EventStaffGrant
from apps.events.models_website import EventPage, EventPageAsset, EventPageSection
from apps.events.services_clone import duplicate_event
from apps.events.services_website import save_content
from apps.events.services_website_assets import upload_asset, delete_asset
from apps.events.website_projection import project
from apps.evidence.storage import StorageUnavailable
from apps.makerspaces import website_assets, limits
from tests.events.website_helpers import website_fixture, section, content, grantee, staff_url
from tests.events.collab_helpers import client_for
from tests.events.website_parity_helpers import metadata, profile

pytestmark = pytest.mark.django_db(transaction=True)


def image_bytes():
    result = BytesIO()
    Image.new("RGB", (12, 12), "red").save(result, format="PNG")
    return result.getvalue()


@pytest.fixture
def objects(monkeypatch):
    values = {}
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    monkeypatch.setattr(limits, "resource_limit", lambda *args: 100_000)
    monkeypatch.setattr(website_assets, "_put", lambda key, data, mime: values.__setitem__(key, data))
    monkeypatch.setattr(website_assets, "object_size", lambda key: len(values[key]) if key in values else None)
    monkeypatch.setattr(website_assets, "copy_object", lambda source, target: values.__setitem__(target, values[source]))
    monkeypatch.setattr(website_assets, "delete_object", lambda key: values.pop(key, None) is not False)
    return values


def upload(event, actor, **kwargs):
    return upload_asset(event, actor=actor, file=SimpleUploadedFile("image.png", image_bytes(), content_type="image/png"), alt_text="Portrait", **kwargs)


def test_upload_reencodes_to_owned_private_webp_and_audits(objects):
    space, manager, event, page, _ = website_fixture()
    asset = upload(event, manager)
    assert asset.object_key.startswith(f"events/website/{space.pk}/{page.pk}/")
    assert set(objects) == {asset.object_key}
    assert objects[asset.object_key][:4] == b"RIFF"
    assert not any(key.startswith("staging/") for key in objects)
    assert AuditLog.objects.filter(action="event.website_asset_saved").exists()


@pytest.mark.parametrize("data", [b"<svg><script>alert(1)</script></svg>", b"not an image", b"x" * (5_000_000 + 1)])
def test_spoofed_type_and_size_are_refused_without_writes(data, objects):
    _, manager, event, _, _ = website_fixture()
    with pytest.raises(ValidationError):
        upload_asset(event, actor=manager, file=SimpleUploadedFile("fake.png", data, content_type="image/png"), alt_text="Fake")
    assert not objects and not EventPageAsset.objects.exists()


def test_pixel_bomb_is_rejected_before_byte_sniff(monkeypatch):
    result = BytesIO(); Image.new("RGB", (5000, 4000)).save(result, format="PNG")
    sniff = Mock()
    monkeypatch.setattr(website_assets, "image_mime_from_bytes", sniff)
    with pytest.raises(ValidationError): website_assets.webp(result.getvalue())
    sniff.assert_not_called()


def test_animated_images_are_refused():
    result = BytesIO()
    Image.new("RGB", (3, 3), "red").save(result, format="WEBP", save_all=True,
        append_images=[Image.new("RGB", (3, 3), "blue")], duration=100, loop=0)
    with pytest.raises(ValidationError): website_assets.webp(result.getvalue())


def test_replace_keeps_retained_bytes_and_only_unpinned_assets_can_be_deleted(objects):
    _, manager, event, page, speaker = website_fixture()
    old = upload(event, manager)
    speaker.asset = old; speaker.save(update_fields=["asset"])
    new = upload(event, manager, replace_id=old.pk)
    speaker.refresh_from_db()
    assert speaker.asset_id == new.pk
    assert old.object_key in objects
    delete_asset(event, old.pk, actor=manager)
    with pytest.raises(ValidationError):
        delete_asset(event, new.pk, actor=manager)
    speaker.refresh_from_db()
    assert speaker.asset_id == new.pk
    assert set(objects) == {new.object_key}


def test_failed_upload_cleans_new_keys_and_rolls_back_quota(monkeypatch, objects):
    space, manager, event, page, _ = website_fixture()
    before = space.storage_bytes_used
    original = website_assets._put
    def fail_final(key, data, mime):
        original(key, data, mime)
        if not key.startswith("staging/"): raise StorageUnavailable()
    monkeypatch.setattr(website_assets, "_put", fail_final)
    with pytest.raises(StorageUnavailable): upload(event, manager)
    space.refresh_from_db()
    assert space.storage_bytes_used == before
    assert not EventPageAsset.objects.exists() and not objects


def test_quota_refusal_and_delete_failure_do_not_grant_free_storage(monkeypatch, objects):
    _, manager, event, _, _ = website_fixture()
    monkeypatch.setattr(limits, "add_storage", Mock(side_effect=ValidationError("quota")))
    with pytest.raises(ValidationError): upload(event, manager)
    assert not objects
    free = Mock(); monkeypatch.setattr(limits, "free_storage", free)
    monkeypatch.setattr(website_assets, "delete_object", Mock(side_effect=StorageUnavailable()))
    with pytest.raises(StorageUnavailable): website_assets.release(event.makerspace, "key", 30)
    free.assert_not_called()


def test_clone_copies_every_asset_to_fresh_keys_and_starts_unreleased(objects):
    _, manager, event, page, speaker = website_fixture()
    for key, value in metadata().items():
        setattr(page, key, value)
    page.save(update_fields=list(metadata()))
    for key, value in profile().items():
        setattr(speaker, key, value)
    original = upload(event, manager)
    speaker.asset = original; speaker.save(update_fields=["asset", *profile()])
    clone = duplicate_event(event, actor=manager)
    copy = clone.website_page
    assert clone.status == "draft" and not copy.released
    page.refresh_from_db()
    assert page.revision > 1 and copy.revision == 1
    cloned = copy.assets.get()
    assert cloned.object_key != original.object_key
    assert objects[cloned.object_key] == objects[original.object_key]
    assert copy.sections.get().asset_id == cloned.pk
    assert all(getattr(copy, key) == value for key, value in metadata().items())
    assert all(getattr(copy.sections.get(), key) == value for key, value in profile().items())
    with pytest.raises(ValidationError):
        delete_asset(clone, cloned.pk, actor=manager)
    assert original.object_key in objects


def series_inheritance(event, page):
    start = event.starts_at
    series = EventSeries.objects.create(makerspace=event.makerspace, title="Series", recurrence_timezone="UTC",
        dtstart_local_date=start.date(), dtstart_local_time=start.timetz().replace(tzinfo=None),
        recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=120, status="published")
    remove_page(page)
    event.series = series; event.series_revision = 1; event.series_occurrence_key = "first"
    event.save(update_fields=["series", "series_revision", "series_occurrence_key"])
    return make_page(makerspace=event.makerspace, series=series, released=True)


@pytest.mark.parametrize("revision", [1, 2, 7])
def test_occurrence_cow_rejects_stale_inherited_save_without_assets(revision):
    _, manager, event, old_page, _ = website_fixture()
    inherited = series_inheritance(event, old_page)
    inherited.revision = revision
    inherited.save(update_fields=["revision"])
    EventPageSection.objects.create(page=inherited, kind="intro", slug="intro",
        title="Series content", visibility="published")
    first = project(event)
    stale = deepcopy(first)
    assert first["inherited"] and first["revision"] == revision
    first["sections"][0]["title"] = "First editor's saved content"
    save_content(event, actor=manager, data=first)
    saved = project(event)
    assert saved["revision"] == revision + 1 and not saved["inherited"]
    assert not saved["released"] and saved["assets"] == []

    stale["sections"][0]["title"] = "Second editor's stale content"
    with pytest.raises(ValidationError) as error:
        save_content(event, actor=manager, data=stale)
    assert "revision" in error.value.detail
    assert project(event) == saved
    inherited.refresh_from_db()
    assert inherited.revision == revision and inherited.released
    assert inherited.sections.get().title == "Series content"
    assert AuditLog.objects.filter(action="event.website_saved").count() == 1

    saved["sections"][0]["title"] = "Reloaded editor's content"
    save_content(event, actor=manager, data=saved)
    assert project(event)["revision"] == revision + 2
    assert EventPage.objects.get(event=event).sections.get().title == "Reloaded editor's content"


def test_occurrence_cow_maps_exact_asset_ids_even_when_section_renamed(objects):
    _, manager, event, old_page, _ = website_fixture()
    page = series_inheritance(event, old_page)
    for key, value in metadata().items():
        setattr(page, key, value)
    page.save(update_fields=list(metadata()))
    asset = EventPageAsset.objects.create(page=page,
        object_key=f"events/website/{event.makerspace_id}/{page.pk}/source.webp", size_bytes=4, alt_text="Source")
    objects[asset.object_key] = b"webp"
    EventPageSection.objects.create(page=page, kind="speaker", slug="old", title="Old", asset=asset,
                                    visibility="published", **profile())
    save_content(event, actor=manager, data=content(page, [section("renamed", "speaker", asset_id=asset.pk, **profile())]))
    override = EventPage.objects.get(event=event)
    assert not override.released and page.released
    assert override.sections.get().asset_id != asset.pk
    assert override.sections.get().asset.page_id == override.pk
    assert all(getattr(override, key) == value for key, value in metadata().items())
    assert all(getattr(override.sections.get(), key) == value for key, value in profile().items())
    assert len(objects) == 2


def test_readonly_noop_cannot_create_private_override_or_copy_bytes(objects):
    space, _, event, page, _ = website_fixture()
    inherited = series_inheritance(event, page)
    user, _ = grantee(space, event, "check_in")
    assert client_for(user).put(staff_url(event), project(event), format="json").status_code == 403
    assert not EventPage.objects.filter(event=event).exists()
    assert inherited.released and not objects


@pytest.mark.parametrize("rollback", [False, True])
def test_recurrence_edit_retires_occurrences_with_saved_history(objects, rollback, monkeypatch):
    """Pages: an occurrence with a saved page revision is retired, never deleted, so its
    assets and bytes stay. Events programme: update_series owns its transaction, so the
    in-transaction checks and the injected rollback run from its final audit write."""
    from apps.events.services_series import create_series, update_series
    space, manager, survivor, _, _ = website_fixture()
    retained = upload(survivor, manager)
    series, occurrences = create_series(
        makerspace=space, actor=manager, title="Draft series", registration_audience="accounts",
        recurrence_timezone="UTC", dtstart_local_date=survivor.starts_at.date(),
        dtstart_local_time=survivor.starts_at.time(), recurrence_rule="FREQ=DAILY;COUNT=2",
        duration_minutes=120,
    )
    assert len(occurrences) == 2
    kept = [upload(occurrences[0], manager), upload(occurrences[0], manager), upload(occurrences[1], manager)]
    # The series template and an unrelated event must retain their own bytes/quota.
    template = upload(series, manager)
    space.refresh_from_db()
    before = space.storage_bytes_used
    original_ids = [event.pk for event in occurrences]

    class Rollback(Exception):
        pass

    from apps.events import services_series_update
    real_record = services_series_update.audit.record
    seen = {}

    def last_write(actor, action, **kwargs):
        result = real_record(actor, action, **kwargs)
        if action == "event.series_updated":
            seen["removed"] = kwargs["meta"]["removed_ids"]
            assert EventPage.objects.filter(event_id__in=original_ids).count() == 2
            assert all(asset.object_key in objects for asset in kept)
            if rollback:
                raise Rollback()
        return result

    monkeypatch.setattr(services_series_update.audit, "record", last_write)
    try:
        update_series(series, actor=manager, recurrence_rule="FREQ=DAILY;COUNT=3")
    except Rollback:
        pass
    monkeypatch.setattr(services_series_update.audit, "record", real_record)
    assert seen["removed"] == []
    space.refresh_from_db()
    assert retained.object_key in objects and template.object_key in objects
    assert EventPage.objects.filter(event_id__in=original_ids).count() == 2
    assert all(asset.object_key in objects for asset in kept)
    assert EventPageAsset.objects.filter(pk__in=[asset.pk for asset in kept]).count() == 3
    assert space.storage_bytes_used == before
