"""Exercise complete page metadata through authority, API and public projections."""

from datetime import timedelta

import pytest
from django.http import HttpResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.models_website import EventPageAsset
from apps.events.services_website import save_content, set_delay
from apps.events.website_projection import project
from tests.events.collab_helpers import client_for
from tests.events.website_helpers import content, grantee, section, session, staff_url, url, website_fixture
from tests.events.website_parity_helpers import metadata, profile
from tests.events.website_helpers import snapshot

pytestmark = pytest.mark.django_db(transaction=True)


def test_page_profiles_sponsors_highlights_and_venue_roundtrip_through_both_apis():
    _, actor, event, page, _ = website_fixture()
    photo = EventPageAsset.objects.create(page=page, object_key="private-portrait", size_bytes=40, alt_text="Ada speaking")
    logo = EventPageAsset.objects.create(page=page, object_key="private-logo", size_bytes=20, alt_text="Community Lab")
    sections = [section("ada", "speaker", asset_id=photo.pk, **profile()),
                section("lab", "sponsor", sponsor_tier="platinum", asset_id=logo.pk),
                section("workshops", "highlight", icon="wrench", body="Build together."),
                section("main-room", "room")]
    response = client_for(actor).put(staff_url(event), {**content(page, sections), **metadata()}, format="json")
    assert response.status_code == 200, response.data
    for key, value in metadata().items():
        assert response.data[key] == value
    page.refresh_from_db()
    assert page.venue == metadata()["venue"] and page.revision == 2
    assert AuditLog.objects.filter(action="event.website_saved", target_id=str(page.pk)).exists()
    snapshot(page, released=True)
    public = APIClient().get(url(event))
    assert public.status_code == 200
    for key, value in metadata().items():
        assert public.data[key] == value
    assert "private-portrait" not in str(public.data) and "object_key" not in str(public.data)
    speaker = APIClient().get(url(event, "speakers/ada/"))
    assert speaker.status_code == 200
    assert all(speaker.data[key] == value for key, value in profile().items())
    assert speaker.data["image_url"] == url(event, f"assets/{photo.pk}/")
    assert speaker.data["image_alt_text"] == "Ada speaking"
    sponsors = [row for row in public.data["sections"] if row["kind"] == "sponsor"]
    assert sponsors[0]["sponsor_tier"] == "platinum"
    assert sponsors[0]["image_url"] == url(event, f"assets/{logo.pk}/")
    highlight = next(row for row in public.data["sections"] if row["kind"] == "highlight")
    assert (highlight["icon"], highlight["body"]) == ("wrench", "Build together.")


def test_legacy_payload_omitting_page_metadata_preserves_saved_content():
    _, actor, event, page, _ = website_fixture()
    save_content(event, actor=actor, data={**content(page, [section()]), **metadata()})
    page.refresh_from_db()
    save_content(event, actor=actor, data=content(page, [section(title="Changed introduction")]))
    page.refresh_from_db()
    assert all(getattr(page, key) == value for key, value in metadata().items())
    assert page.sections.get().title == "Changed introduction"


def legacy_sections(rows):
    fields = {"kind", "slug", "title", "body", "url", "asset_id", "visibility", "position"}
    return [{key: value for key, value in row.items() if key in fields} for row in rows]


def save_curated_sections(actor, event, page):
    rows = [section("ada", "speaker", **profile()),
            section("lab", "sponsor", sponsor_tier="platinum"),
            section("workshops", "highlight", icon="wrench", body="Make together.")]
    response = client_for(actor).put(staff_url(event), content(page, rows), format="json")
    assert response.status_code == 200, response.data


def assert_curated_sections_survive(event):
    rows = {row["slug"]: row for row in project(event)["sections"]}
    assert all(rows["ada"][key] == value for key, value in profile().items())
    assert rows["lab"]["sponsor_tier"] == "platinum"
    assert rows["workshops"]["icon"] == "wrench"


def test_legacy_section_payload_preserves_existing_profile_tier_and_icon():
    _, actor, event, page, _ = website_fixture()
    save_curated_sections(actor, event, page)
    data = project(event)
    data["sections"] = legacy_sections(data["sections"])
    data["sections"][0]["body"] = "Updated by an older client."
    response = client_for(actor).put(staff_url(event), data, format="json")
    assert response.status_code == 200, response.data
    assert_curated_sections_survive(event)
    assert project(event)["sections"][0]["body"] == "Updated by an older client."


def test_schedule_only_legacy_client_preserves_curated_fields_without_detail_permission():
    space, actor, event, page, _ = website_fixture()
    save_curated_sections(actor, event, page)
    publisher, _ = grantee(space, event, "publish_schedule")
    data = project(event)
    data["sections"] = legacy_sections(data["sections"])
    data["sessions"] = [session(event, speakers=["ada"])]
    response = client_for(publisher).put(staff_url(event), data, format="json")
    assert response.status_code == 200, response.data
    assert_curated_sections_survive(event)
    assert project(event)["sessions"][0]["speakers"] == ["ada"]


def test_explicit_blank_profile_and_icon_clear_while_omitted_values_survive():
    _, actor, event, page, _ = website_fixture()
    save_curated_sections(actor, event, page)
    data = project(event)
    data["sections"] = legacy_sections(data["sections"])
    data["sections"][0]["headline"] = ""
    data["sections"][0]["website_url"] = ""
    data["sections"][2]["icon"] = ""
    response = client_for(actor).put(staff_url(event), data, format="json")
    assert response.status_code == 200, response.data
    rows = {row["slug"]: row for row in project(event)["sections"]}
    assert rows["ada"]["headline"] == "" and rows["ada"]["website_url"] == ""
    assert rows["ada"]["organization"] == profile()["organization"]
    assert rows["lab"]["sponsor_tier"] == "platinum" and rows["workshops"]["icon"] == ""


def test_explicit_empty_page_values_clear_content():
    _, actor, event, page, _ = website_fixture()
    save_content(event, actor=actor, data={**content(page), **metadata()})
    page.refresh_from_db()
    save_content(event, actor=actor, data={**content(page), "tagline": "", "accent_color": "", "venue": None})
    page.refresh_from_db()
    assert page.tagline == "" and page.accent_color == "" and page.venue is None


@pytest.mark.parametrize("field,value", list(metadata().items()))
def test_schedule_publisher_cannot_smuggle_page_metadata(field, value):
    space, _, event, page, _ = website_fixture()
    publisher, _ = grantee(space, event, "publish_schedule")
    data = project(event)
    data[field] = value if field != "section_enabled" else {**value, "ABOUT": False}
    response = client_for(publisher).put(staff_url(event), data, format="json")
    assert response.status_code == 403, response.data
    page.refresh_from_db()
    assert page.revision == 1


@pytest.mark.parametrize("field,value", list(profile().items()))
def test_schedule_publisher_cannot_smuggle_new_speaker_fields(field, value):
    space, _, event, page, _ = website_fixture()
    publisher, _ = grantee(space, event, "publish_schedule")
    data = project(event)
    data["sections"][0][field] = value
    assert client_for(publisher).put(staff_url(event), data, format="json").status_code == 403
    assert project(event)["revision"] == 1


@pytest.mark.parametrize("slug,field,value", [("lab", "sponsor_tier", "gold"), ("workshops", "icon", "star")])
def test_legacy_schedule_publisher_cannot_explicitly_change_curated_fields(slug, field, value):
    space, actor, event, page, _ = website_fixture()
    save_curated_sections(actor, event, page)
    publisher, _ = grantee(space, event, "publish_schedule")
    data = project(event)
    data["sections"] = legacy_sections(data["sections"])
    next(row for row in data["sections"] if row["slug"] == slug)[field] = value
    data["sessions"] = [session(event)]
    assert client_for(publisher).put(staff_url(event), data, format="json").status_code == 403
    assert_curated_sections_survive(event)
    assert project(event)["sessions"] == []


def test_revoked_detail_grant_cannot_edit_new_metadata_with_stale_actor():
    from django.utils import timezone
    space, _, event, page, _ = website_fixture()
    editor, grant = grantee(space, event, "edit_details")
    grant.revoked_at = timezone.now()
    grant.save(update_fields=["revoked_at"])
    with pytest.raises(PermissionDenied):
        save_content(event, actor=editor, data={**content(page), **metadata()})
    page.refresh_from_db()
    assert page.revision == 1 and page.tagline == ""


def test_group_toggles_hide_direct_children_and_sessions_without_erasing_editor_data(monkeypatch):
    _, actor, event, page, _ = website_fixture()
    asset = EventPageAsset.objects.create(page=page, object_key="private-shared", size_bytes=20, alt_text="Shared portrait")
    rows = [section("ada", "speaker", asset_id=asset.pk, **profile()),
            section("partner", "sponsor", asset_id=asset.pk), section("benefit", "highlight", icon="tools"),
            section("workshop", "resource", url="https://example.com/resources")]
    settings = metadata()
    settings["section_enabled"].update(SPEAKERS=False, SPONSORS=False, HIGHLIGHTS=False, VENUE=False, SCHEDULE=False)
    save_content(event, actor=actor, data={**content(page, rows, [session(event, speakers=["ada"])]), **settings})
    page.refresh_from_db()
    snapshot(page, released=True)
    response = APIClient().get(url(event))
    assert response.status_code == 200
    assert [row["slug"] for row in response.data["sections"]] == ["workshop"]
    assert response.data["venue"] is None and response.data["sessions"] == []
    assert APIClient().get(url(event, "schedule/")).data == []
    for suffix in ("speakers/ada/", "sections/ada/", "sections/partner/", "sections/benefit/", "sessions/talk/", f"assets/{asset.pk}/"):
        assert APIClient().get(url(event, suffix)).status_code == 404, suffix
    editor_data = project(event)
    assert len(editor_data["sections"]) == 4 and len(editor_data["sessions"]) == 1
    assert editor_data["venue"] == settings["venue"]
    assert editor_data["sections"][0]["headline"] == profile()["headline"]
    page.refresh_from_db()
    # The same private bytes are public when a separately enabled, published row references them.
    resource = page.sections.get(slug="workshop")
    resource.asset = asset
    resource.save(update_fields=["asset"])
    snapshot(page, released=True)
    monkeypatch.setattr("apps.events.views_website_public.image_response", lambda _: HttpResponse(b"webp"))
    assert APIClient().get(url(event, f"assets/{asset.pk}/")).status_code == 200
    resource.visibility = "draft"
    resource.save(update_fields=["visibility"])
    snapshot(page, released=True)
    assert APIClient().get(url(event, f"assets/{asset.pk}/")).status_code == 404


def test_speaker_toggle_redacts_session_speaker_references_but_keeps_programme():
    _, actor, event, page, _ = website_fixture()
    data = {**content(page, [section("ada", "speaker")], [session(event, speakers=["ada"])]), **metadata()}
    data["section_enabled"]["SPEAKERS"] = False
    save_content(event, actor=actor, data=data)
    page.refresh_from_db()
    snapshot(page, released=True)
    assert APIClient().get(url(event, "sessions/talk/")).data["speakers"] == []
    assert project(event)["sessions"][0]["speakers"] == ["ada"]


def test_parallel_tracks_multiple_speakers_and_delay_public_pages():
    space, actor, event, page, _ = website_fixture()
    rows = [section("first", "track"), section("parallel", "track"), section("ada", "speaker"), section("grace", "speaker")]
    schedule = [session(event, "joint", track="first", speakers=["ada", "grace"]),
                session(event, "parallel", track="parallel"),
                session(event, "later", track="first", starts_at=event.starts_at + timedelta(minutes=45),
                        ends_at=event.starts_at + timedelta(minutes=60))]
    save_content(event, actor=actor, data=content(page, rows, schedule))
    page.refresh_from_db()
    snapshot(page, released=True)
    editor, _ = grantee(space, event, "edit_details")
    with pytest.raises(PermissionDenied):
        set_delay(event, "joint", actor=editor, minutes=15)
    publisher, _ = grantee(space, event, "publish_schedule")
    set_delay(event, "joint", actor=publisher, minutes=15)
    response = APIClient().get(url(event, "schedule/"))
    assert response.status_code == 200 and len(response.data) == 3
    joint = APIClient().get(url(event, "sessions/joint/"))
    assert joint.status_code == 200 and set(joint.data["speakers"]) == {"ada", "grace"}
    public = project(event, public=True)["sessions"]
    shifts = {row["slug"]: row["effective_starts_at"] - row["starts_at"] for row in public}
    assert shifts == {"joint": timedelta(minutes=15), "parallel": timedelta(), "later": timedelta(minutes=15)}
    assert AuditLog.objects.filter(action="event.website_delay_changed").exists()
