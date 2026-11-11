"""Round 5 (events): consent carry-forward, window-trigger locks, speaker order,
image replacement, scope-safe core detail and one public-site decision."""

from contextlib import ExitStack
from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.events.models import Event, EventSeries
from apps.events.models_website import EventPage, EventPageAsset
from apps.events.services_website import save_content, set_release
from apps.events.services_website_assets import upload_asset
from apps.events.website_projection import project
from apps.makerspaces import limits, website_assets
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.models_profiles import MemberProfile
from apps.makerspaces.public_page_contract import empty_document
from tests.events.collab_helpers import make_member
from tests.events.website_helpers import grantee, make_page, make_session, section, session
from tests.public_pages.l1b_threads import database_worker, wait_for_blocked

pytestmark = pytest.mark.django_db(transaction=True)


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
    data = BytesIO()
    Image.new("RGB", (12, 12), "red").save(data, format="PNG")
    return upload_asset(event, actor=actor, file=SimpleUploadedFile("image.png", data.getvalue(), content_type="image/png"),
                        alt_text="Portrait", **kwargs)


def public_profile(space, username="member"):
    if "membership" not in space.enabled_modules:
        space.enabled_modules += ["membership"]
        space.save(update_fields=["enabled_modules"])
    user = make_member(space, username=username)
    return MemberProfile.objects.create(membership=MakerspaceMembership.objects.get(makerspace=space, user=user),
                                        public_visible=True, public_consented_at=timezone.now())


def team(slot, profile):
    return {"id": str(uuid4()), "type": "team", "enabled": True, "payload": {"title": "Team", "entries": [
        {"id": slot, "kind": "member", "profile_id": profile.pk, "role": "Host"}]}}


# Finding 1: consent gates choosing a member, not re-saving an unchanged one.
@pytest.mark.parametrize("path", ["reschedule", "replace_asset", "duplicate", "schedule_only"])
def test_unchanged_member_slot_survives_profile_going_private(event_owner, objects, path):
    from apps.events.event_permissions import PUBLISH_SCHEDULE
    from apps.events.services_clone import duplicate_event
    from apps.events.services_event_details import update_event
    space, actor, event = event_owner
    profile = public_profile(space)
    other = public_profile(space, "other")
    slot = str(uuid4())
    editorial = empty_document("event")
    editorial["sections"].append(team(slot, profile))
    save_content(event, actor=actor, data={"revision": 0, "sections": [], "sessions": [session(event)],
                                           "editorial_document": editorial})
    old = upload(event, actor)
    page = EventPage.objects.get(event=event)
    first_draft = page.draft_revision_id
    for withdrawn in (profile, other):
        withdrawn.public_visible = False
        withdrawn.save(update_fields=["public_visible"])
    if path == "reschedule":
        update_event(event, actor=actor, starts_at=event.starts_at - timedelta(hours=1))
    elif path == "replace_asset":
        upload(event, actor, replace_id=old.pk)
    elif path == "duplicate":
        clone = duplicate_event(event, actor=actor)
        page = EventPage.objects.get(event=clone)
    else:
        scheduler, _ = grantee(space, event, PUBLISH_SCHEDULE)
        data = project(event)
        data["sessions"][0]["title"] = "Moved talk"
        save_content(event, actor=scheduler, data=data)
    page.refresh_from_db()
    assert page.draft_revision_id != first_draft
    assert page.draft_revision.member_references.get(slot=slot).profile_id == profile.pk
    # Choosing a private profile in a NEW slot is still refused.
    data = project(event)
    members = next(row for row in data["editorial_document"]["sections"] if row["type"] == "team")
    members["payload"]["entries"].append({"id": str(uuid4()), "kind": "member", "profile_id": other.pk, "role": "Guest"})
    with pytest.raises(ValidationError, match="currently public member profiles"):
        save_content(event, actor=actor, data=data)


# Finding 2: the windows trigger is column-scoped and locks occurrences in id order.
def series_with_released_page():
    from tests.events.ticketing_helpers import event_space
    from tests.events.collab_helpers import make_staff
    space = event_space("window-locks")
    space.enabled_features += ["events.website"]
    space.save(update_fields=["enabled_features"])
    actor = make_staff(space)
    start = (timezone.now() + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)
    series = EventSeries.objects.create(
        makerspace=space, title="Series", recurrence_timezone="UTC", dtstart_local_date=start.date(),
        dtstart_local_time=start.time(), recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=120,
        registration_audience="accounts", status="published")
    occurrences = [Event.objects.create(
        makerspace=space, series=series, series_revision=1, title="Series", is_public=True, status="published",
        series_occurrence_key=f"1:{start + timedelta(days=day):%Y%m%dT%H%M%S}", registration_audience="accounts",
        starts_at=start + timedelta(days=day), ends_at=start + timedelta(days=day, hours=2)) for day in range(2)]
    page = make_page(makerspace=space, series=series, released=True)
    make_session(page=page, slug="talk", title="Talk", visibility="published",
                 starts_at=start, ends_at=start + timedelta(minutes=30))
    return actor, series, occurrences


def test_concurrent_occurrence_cancels_and_series_update_do_not_deadlock():
    from apps.events import services
    from apps.events.services_series_update import update_series
    actor, series, (first, second) = series_with_released_page()
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE tgname='event_snapshot_windows' "
                       "AND tgrelid='events_event'::regclass")
        assert "UPDATE OF starts_at, ends_at, series_id" in cursor.fetchone()[0]
    # Window inputs still re-check the released programme.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Event.objects.filter(pk=first.pk).update(ends_at=first.starts_at + timedelta(minutes=10))
    # Event commands own their transaction (events programme write boundary), so the
    # held sibling lock lives in this test's transaction and each command runs outside it.
    with ExitStack() as stack:
        with transaction.atomic():
            Event.objects.select_for_update().get(pk=second.pk)
            # A status-only commit must not lock the series or sibling occurrences.
            cancel, _ = stack.enter_context(database_worker(
                lambda: services.cancel(first, actor=actor, notify=False)))
            cancel.result(timeout=15)
    services.cancel(second, actor=actor, notify=False)
    with ExitStack() as stack:
        with transaction.atomic():
            Event.objects.select_for_update().get(pk=second.pk)
            edit, pid = stack.enter_context(database_worker(
                lambda: update_series(series, actor=actor, description="Updated")))
            wait_for_blocked(pid)
        edit.result(timeout=15)
    assert set(Event.objects.filter(pk__in=(first.pk, second.pk)).values_list("status", flat=True)) == {"cancelled"}
    series.refresh_from_db()
    assert series.description == "Updated"


# Finding 3: speakers keep authored order; verifiers ignore heap order of stored drafts.
def test_speaker_order_is_stable_and_verifiers_tolerate_stored_order(event_owner):
    from apps.backup.event_page_draft_verification import verify_working_draft
    from apps.backup.build_errors import BackupBuildError
    from apps.events.website_revisions import append_snapshot, working_document
    from apps.tenant_migration.insertion_errors import ImportVerificationError
    from apps.tenant_migration.public_page_verification import verify_event_draft
    space, actor, event = event_owner
    speakers = [section("zed", "speaker"), section("ada", "speaker"), section("max", "speaker")]
    save_content(event, actor=actor, data={"revision": 0, "sections": speakers,
                                           "sessions": [session(event, speakers=["zed", "ada", "max"])]})
    page = EventPage.objects.get(event=event)
    assert project(event)["sessions"][0]["speakers"] == ["zed", "ada", "max"]
    assert page.draft_revision.document["sessions"][0]["speakers"] == ["zed", "ada", "max"]

    def store(order):
        document = working_document(page)
        document["sessions"][0]["speakers"] = order
        with transaction.atomic():
            page.draft_revision = append_snapshot(page, document=document)
            page.save(update_fields=["draft_revision"])

    store(["max", "zed", "ada"])  # A draft saved while heap order was nondeterministic.
    verify_working_draft(page)
    verify_event_draft(page)
    store(["zed", "ada"])  # Real speaker drift still fails both verifiers.
    with pytest.raises(BackupBuildError, match="working website differs"):
        verify_working_draft(page)
    with pytest.raises(ImportVerificationError):
        verify_event_draft(page)


# Finding 4: replacing an image remaps the cover and gallery references.
def test_replace_image_remaps_cover_and_gallery(event_owner, objects):
    space, actor, event = event_owner
    save_content(event, actor=actor, data={"revision": 0, "sections": [], "sessions": []})
    old = upload(event, actor)
    keep = upload(event, actor)
    editorial = empty_document("event")
    editorial.update(cover_mode="asset", cover_asset_id=old.pk)
    editorial["sections"].append({"id": str(uuid4()), "type": "gallery", "enabled": True, "payload": {
        "title": "Gallery", "items": [{"asset_id": old.pk, "caption": "One"}, {"asset_id": keep.pk, "caption": "Two"}]}})
    page = EventPage.objects.get(event=event)
    save_content(event, actor=actor, data={"revision": page.revision, "sections": [], "sessions": [],
                                           "editorial_document": editorial})
    new = upload(event, actor, replace_id=old.pk)
    page.refresh_from_db()
    document = page.editorial_document
    assert document["cover_asset_id"] == new.pk
    gallery = next(row for row in document["sections"] if row["type"] == "gallery")
    assert [item["asset_id"] for item in gallery["payload"]["items"]] == [new.pk, keep.pk]
    references = dict(page.draft_revision.asset_references.values_list("slot", "asset_id"))
    assert references["editorial:cover"] == new.pk
    assert old.pk not in references.values() and keep.pk in references.values()


def released_cover(event_owner):
    space, actor, event = event_owner
    save_content(event, actor=actor, data={"revision": 0, "sections": [], "sessions": []})
    page = EventPage.objects.get(event=event)
    asset = EventPageAsset.objects.create(page=page, size_bytes=4, alt_text="Cover",
                                          object_key=f"events/website/{space.pk}/{page.pk}/cover.webp")
    document = empty_document("event")
    document.update(cover_mode="asset", cover_asset_id=asset.pk)
    save_content(event, actor=actor, data={"revision": page.revision, "sections": [], "sessions": [],
                                           "editorial_document": document})
    page.refresh_from_db()
    set_release(event, actor=actor, released=True, revision=page.revision)
    return space, event, asset


# Finding 5: an optional-website scope refusal never 404s the core event detail.
def test_public_event_detail_survives_website_scope_refusal(event_owner):
    space, event, _ = released_cover(event_owner)
    route = f"/api/v1/public/{space.slug}/events/{event.public_token}/"
    baseline = APIClient().get(route)
    assert baseline.status_code == 200 and baseline.json()["website"] is not None
    for origin in ("null", "https://unknown.example.test"):
        response = APIClient().get(route, HTTP_ORIGIN=origin)
        assert response.status_code == 200, origin
        assert response.json()["public_token"] == str(event.public_token)
        assert response.json()["website"] is None


# Finding 6: website JSON, image bytes, cover share and cards share one site decision.
@pytest.mark.parametrize("site_enabled", [True, False])
def test_website_images_follow_the_public_site_decision(event_owner, settings, monkeypatch, site_enabled):
    from apps.events.website_adapter import card
    from apps.evidence import storage
    space, event, asset = released_cover(event_owner)
    monkeypatch.setattr(storage, "object_size", lambda key: 4)
    monkeypatch.setattr(storage, "_client", lambda: SimpleNamespace(get_object=lambda **kw: {"Body": BytesIO(b"webp")}))
    space.public_site_enabled = site_enabled
    space.save(update_fields=["public_site_enabled"])
    event = Event.objects.select_related("makerspace").get(pk=event.pk)
    image = f"/api/v1/public/{space.slug}/events/{event.public_token}/website/assets/{asset.pk}/"
    client = APIClient()
    detail = client.get(f"/api/v1/public/{space.slug}/events/{event.public_token}/")
    assert detail.status_code == 200
    website = client.get(f"/api/v1/public/{space.slug}/events/{event.public_token}/website/")
    expected = 200 if site_enabled else 404
    assert website.status_code == expected
    assert client.get(image).status_code == expected
    assert client.get(f"/share/e/{event.public_token}/cover/").status_code == expected
    assert (detail.json()["website"] is not None) is site_enabled
    card_image = card(event).image_url
    assert (card_image is not None and urlsplit(card_image).path == image) is site_enabled
