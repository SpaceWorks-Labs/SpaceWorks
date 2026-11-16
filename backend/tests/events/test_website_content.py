from tests.events.website_helpers import make_page, make_session
from copy import deepcopy
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.events import services
from apps.events.models import Event, EventSeries
from apps.events.models_website import EventPage, EventPageSection, EventSession, EventSessionSpeaker
from apps.events.services_website import save_content, set_release, set_delay
from apps.events.website_projection import project, window
from tests.events.collab_helpers import client_for
from tests.events.ticketing_helpers import event_space, open_event
from tests.events.website_helpers import website_fixture, section, session, content, grantee, staff_url, snapshot

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("permission,allowed", [("edit_details", True), ("publish_schedule", False),
    ("manage_registrations", False), ("manage_invitations", False), ("check_in", False)])
def test_section_permission_matrix(permission, allowed):
    space, _, event, page, _ = website_fixture()
    user, _ = grantee(space, event, permission)
    response = client_for(user).put(staff_url(event), content(page, [section()]), format="json")
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize("permission,allowed", [("edit_details", False), ("publish_schedule", True),
    ("manage_registrations", False), ("check_in", False)])
def test_release_permission_matrix(permission, allowed):
    space, _, event, page, _ = website_fixture()
    user, _ = grantee(space, event, permission)
    response = client_for(user).post(staff_url(event, "release/"),
        {"released": False, "revision": page.revision}, format="json")
    assert response.status_code == (200 if allowed else 403)
    page.refresh_from_db()
    assert page.released is (not allowed)


def test_schedule_grant_can_edit_schedule_without_edit_details():
    space, _, event, page, _ = website_fixture()
    user, _ = grantee(space, event, "publish_schedule")
    data = project(event)
    data["sessions"] = [session(event)]
    assert client_for(user).put(staff_url(event), data, format="json").status_code == 200


def test_detail_grant_cannot_smuggle_schedule_or_revoked_grant():
    space, _, event, page, _ = website_fixture()
    user, grant = grantee(space, event, "edit_details")
    data = project(event)
    data["sessions"] = [session(event)]
    with pytest.raises(ValidationError):
        save_content(event, actor=user, data=data)
    grant.revoked_at = timezone.now()
    grant.save(update_fields=["revoked_at"])
    with pytest.raises(PermissionDenied):
        save_content(event, actor=user, data=project(event))


def test_noop_requires_real_editor_and_refuses_foreign_tenant():
    space, manager, event, page, _ = website_fixture()
    user, _ = grantee(space, event, "check_in")
    response = client_for(user).put(staff_url(event), project(event), format="json")
    assert response.status_code == 403
    foreign = open_event(event_space("foreign-website"))
    assert client_for(manager).put(staff_url(foreign), {"revision": 0, "sections": [], "sessions": []}, format="json").status_code == 404
    assert EventPage.objects.get(pk=page.pk).revision == 1


@pytest.mark.parametrize("change", ["duplicate_slug", "wrong_track", "foreign_image", "negative_window", "outside_window", "duplicate_speaker"])
def test_content_validation_rolls_back_everything(change):
    space, manager, event, page, _ = website_fixture()
    sections = [section("speaker", "speaker")]
    sessions = [session(event, speakers=["speaker"])]
    if change == "duplicate_slug": sections += [section("speaker")]
    if change == "wrong_track": sessions[0]["track"] = "speaker"
    if change == "foreign_image": sections[0]["asset_id"] = 999999
    if change == "negative_window": sessions[0]["ends_at"] = event.starts_at
    if change == "outside_window": sessions[0]["ends_at"] = event.ends_at + timedelta(seconds=1)
    if change == "duplicate_speaker": sessions[0]["speakers"] *= 2
    with pytest.raises(ValidationError):
        save_content(event, actor=manager, data=content(page, sections, sessions))
    page.refresh_from_db()
    assert page.revision == 1
    assert page.sections.get().slug == "ada"
    assert not AuditLog.objects.filter(action="event.website_saved").exists()


def test_stale_revision_and_terminal_mutations_refused():
    _, manager, event, page, _ = website_fixture()
    with pytest.raises(ValidationError):
        save_content(event, actor=manager, data={"revision": 999, "sections": [], "sessions": []})
    event.status = "cancelled"
    event.save(update_fields=["status"])
    with pytest.raises(ValidationError):
        set_release(event, actor=manager, released=False, revision=1)


def test_publish_requires_explicit_tick_and_is_atomic(monkeypatch):
    _, manager, event, page, _ = website_fixture(released=False)
    monkeypatch.setattr("apps.events.services.notify_event_lifecycle", lambda *a, **k: None)
    event.status = "draft"
    event.save(update_fields=["status"])
    with pytest.raises(ValidationError):
        services.publish(event, actor=manager, publish_website=True, website_revision=999)
    event.refresh_from_db()
    assert event.status == "draft"
    services.publish(event, actor=manager)
    page.refresh_from_db()
    assert not page.released
    event.status = "draft"
    event.save(update_fields=["status"])
    services.publish(event, actor=manager, publish_website=True, website_revision=page.revision)
    page.refresh_from_db()
    assert page.released
    assert AuditLog.objects.filter(action="event.website_released").exists()


@pytest.mark.parametrize("payload", [123, [{}], [], "text", True, None, {"unexpected": True}])
def test_publish_rejects_invalid_json_shapes_without_mutation(payload):
    _, manager, event, page, _ = website_fixture(released=False)
    event.status = "draft"
    event.save(update_fields=["status"])
    import json
    response = client_for(manager).generic(
        "POST", f"/api/v1/admin/events/{event.pk}/publish/",
        data=json.dumps(payload), content_type="application/json",
    )
    assert response.status_code == 400
    event.refresh_from_db()
    page.refresh_from_db()
    assert event.status == "draft" and not page.released
    assert not AuditLog.objects.filter(action__in=["event.published", "event.website_released"]).exists()


def test_delays_are_track_running_maximum_and_keep_planned_times():
    _, manager, event, page, _ = website_fixture()
    save_content(event, actor=manager, data=content(page, [section("track", "track")], [
        session(event, "a", track="track"), session(event, "b", starts_at=event.starts_at + timedelta(minutes=45), ends_at=event.starts_at + timedelta(minutes=60), track="track"),
        session(event, "c", starts_at=event.starts_at + timedelta(minutes=70), ends_at=event.ends_at),
    ]))
    set_delay(event, "a", actor=manager, minutes=30)
    set_delay(event, "b", actor=manager, minutes=10)
    rows = project(event)["sessions"]
    assert [(row["effective_starts_at"] - row["starts_at"]).total_seconds() for row in rows] == [1800, 1800, 0]
    assert EventSession.objects.get(page=page, slug="a").starts_at == event.starts_at
    with pytest.raises(ValidationError): set_delay(event, "a", actor=manager, minutes=1441)


@pytest.mark.parametrize("track", [None, "main"])
def test_published_programme_preview_ignores_draft_delays(track):
    _, manager, event, page, _ = website_fixture()
    rows = []
    schedule = [
        ("early-draft", "draft", 60, track),
        ("published-a", "published", 15, track),
        ("middle-draft", "draft", 90, track),
        ("published-b", "published", 5, track),
        ("published-c", "published", 30, track),
        ("published-d", "published", 0, track),
        ("other-track", "published", 0, "other"),
    ]
    for index, (slug, visibility, _, session_track) in enumerate(schedule):
        rows.append(session(event, slug, visibility=visibility, track=session_track,
            starts_at=event.starts_at + timedelta(minutes=index * 10),
            ends_at=event.starts_at + timedelta(minutes=(index + 1) * 10)))
    save_content(event, actor=manager, data=content(page,
        [section("main", "track"), section("other", "track")], rows))
    for slug, _, minutes, _ in schedule:
        if minutes:
            set_delay(event, slug, actor=manager, minutes=minutes)

    staff_rows = project(event)["sessions"]
    preview = [row for row in staff_rows if row["visibility"] == "published"]
    page.refresh_from_db()
    set_release(event, actor=manager, released=True, revision=page.revision)
    public_rows = project(event, public=True)["sessions"]
    assert preview == public_rows
    assert [row["slug"] for row in public_rows] == [
        "published-a", "published-b", "published-c", "published-d", "other-track"]
    for row, minutes in zip(public_rows, [15, 15, 30, 30, 0], strict=True):
        shift = timedelta(minutes=minutes)
        assert row["effective_starts_at"] == row["starts_at"] + shift
        assert row["effective_ends_at"] == row["ends_at"] + shift
        stored = EventSession.objects.get(page=page, slug=row["slug"])
        assert stored.starts_at == row["starts_at"] and stored.ends_at == row["ends_at"]
    drafts = [row for row in staff_rows if row["visibility"] == "draft"]
    assert [row["slug"] for row in drafts] == ["early-draft", "middle-draft"]
    assert [row["effective_starts_at"] - row["starts_at"] for row in drafts] == [
        timedelta(minutes=60), timedelta(minutes=90)]


def test_owner_window_edits_get_typed_error_and_db_backstop():
    _, manager, event, page, _ = website_fixture()
    save_content(event, actor=manager, data=content(page, [], [session(event)]))
    with pytest.raises(ValidationError):
        services.update_event(event, actor=manager, ends_at=event.starts_at + timedelta(minutes=1))
    with pytest.raises(IntegrityError), transaction.atomic():
        Event.objects.filter(pk=event.pk).update(ends_at=event.starts_at + timedelta(minutes=1))


def test_same_page_and_exact_owner_constraints_apply_to_direct_writers():
    space, _, event, page, speaker = website_fixture()
    foreign = open_event(event_space("foreign-page"))
    with pytest.raises(IntegrityError), transaction.atomic():
        make_page(makerspace=space)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_page(makerspace=space, event=foreign)
    other = make_page(makerspace=foreign.makerspace, event=foreign)
    track = EventPageSection.objects.create(page=other, kind="track", slug="t", title="Other")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_session(page=page, track=track, slug="s", title="Bad", starts_at=event.starts_at, ends_at=event.ends_at)
    talk = make_session(page=other, slug="s", title="Talk", starts_at=foreign.starts_at, ends_at=foreign.ends_at)
    with pytest.raises(IntegrityError), transaction.atomic():
        EventSessionSpeaker.objects.create(session=talk, speaker=speaker)
