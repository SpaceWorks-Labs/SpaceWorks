"""Round 3: live operational edits and real membership navigation contracts."""

from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.renderers import JSONRenderer

from apps.events.models_website import EventPage
from apps.events.services_website import save_content, set_delay, set_release
from apps.events.website_projection import project
from apps.makerspaces import public_page_services as pages
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.models_profiles import MemberProfile, PublicHandle
from apps.makerspaces.models import AccountProfile
from apps.makerspaces.public_page_contract import empty_document
from apps.makerspaces.public_page_projected_serializers import PROJECTED_TYPES
from apps.makerspaces.public_page_serializers import PreviewProjection, PublicPageProjection
from tests.events.collab_helpers import make_member
from tests.events.website_helpers import grantee, session

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("withdrawal", ["consent", "deleted"])
@pytest.mark.parametrize("released", [True, False])
def test_schedule_only_delay_preserves_saved_references_after_withdrawal(event_owner, withdrawal, released):
    from apps.backup.event_page_draft_verification import verify_working_draft
    from apps.events.event_permissions import EDIT_DETAILS, PUBLISH_SCHEDULE
    from apps.events import event_authority
    space, actor, event = event_owner
    space.enabled_modules += ["membership"]
    space.save(update_fields=["enabled_modules"])
    user = make_member(space)
    profile = MemberProfile.objects.create(
        membership=MakerspaceMembership.objects.get(makerspace=space, user=user),
        public_visible=True, public_consented_at=timezone.now())
    PublicHandle.objects.create(user=user, profile=profile, handle="delay.member", changed_at=timezone.now())
    # Decision 305: the ACCOUNT profile decides visibility; the per-space row is only a reference token.
    AccountProfile.objects.update_or_create(user=user, defaults={"public_visible": True, "public_consented_at": timezone.now()})
    slot, team = str(uuid4()), str(uuid4())
    editorial = empty_document("event")
    editorial["sections"].append({"id": team, "type": "team", "enabled": True,
        "payload": {"title": "Team", "entries": [
            {"id": slot, "kind": "member", "profile_id": profile.pk, "role": "Host"}]}})
    save_content(event, actor=actor, data={"revision": 0, "sections": [],
        "sessions": [session(event)], "editorial_document": editorial})
    page = EventPage.objects.get(event=event)
    if released:
        set_release(event, actor=actor, released=True, revision=page.revision)
        assert project(event, public=True)["editorial_document"]["sections"][0]["payload"]["entries"]
    # Keep an editorial change in the draft: the delay must never publish it.
    edit = project(event)
    edit["tagline"] = "Unpublished editorial tagline"
    edit["sessions"][0]["title"] = "Draft session title"
    save_content(event, actor=actor, data=edit)
    page.refresh_from_db()
    before_draft = deepcopy(page.draft_revision.document)
    before_public = deepcopy(page.published_revision.document) if released else None
    if withdrawal == "consent":
        profile.public_visible = False
        profile.save(update_fields=["public_visible"])
        AccountProfile.objects.filter(user=user).update(public_visible=False)
    else:
        profile.delete()  # SET_NULL must also survive the snapshot copy.
    schedule_actor, _ = grantee(space, event, PUBLISH_SCHEDULE)
    assert not event_authority.can(schedule_actor, event, EDIT_DETAILS)
    old_version, old_draft, old_public = page.revision, page.draft_revision_id, page.published_revision_id
    set_delay(event, "talk", actor=schedule_actor, minutes=15, revision=old_version,
              session_id=before_draft["sessions"][0]["session_id"])
    page.refresh_from_db()
    before_draft["sessions"][0]["delay_minutes"] = 15
    assert page.draft_revision.document == before_draft
    assert page.draft_revision_id != old_draft and page.revision == old_version + 1
    assert page.sessions.get().delay_minutes == 15
    expected_profile = profile.pk if withdrawal == "consent" else None
    assert page.draft_revision.member_references.get(slot=slot).profile_id == expected_profile
    if released:
        before_public["sessions"][0]["delay_minutes"] = 15
        assert page.published_revision.document == before_public
        assert page.published_revision_id != old_public
        assert page.published_revision.member_references.get(slot=slot).profile_id == expected_profile
        public = project(event, public=True)
        assert public["tagline"] == "" and public["sessions"][0]["title"] == "Talk"
        assert public["sessions"][0]["delay_minutes"] == 15
        assert public["editorial_document"]["sections"][0]["payload"]["entries"] == []
    else:
        assert page.published_revision_id is None
    verify_working_draft(page)


@pytest.mark.parametrize("tenant_domain", [False, True])
def test_member_family_uses_actual_route_in_live_page_and_validated_preview(page_owner, settings, tenant_domain):
    from apps.makerspaces.module_registry import core_module_keys
    from apps.makerspaces.public_page_projection import projection
    settings.PUBLIC_APP_BASE_URL = "https://platform.example.test"
    settings.SPACEWORKS_EDITION = "makerspace"
    space, actor = page_owner
    space.slug, space.name = "lab", "Lab"
    space.enabled_modules = sorted(core_module_keys() | {"events", "bookings", "machines", "membership", "public_inventory"})
    space.enabled_features = ["loans.enabled"]
    space.public_inventory_enabled = True
    # The fixture captures the default (empty) tenant theme; this test is about route mapping.
    space.theme_config = {}
    if tenant_domain:
        space.frontend_domain, space.frontend_domain_status = "tenant.example.test", "verified"
    space.save()
    fixture = json.loads((Path(__file__).parent / "fixtures" / "review-r3.json").read_text())[
        "tenant" if tenant_domain else "platform"]
    document = empty_document("makerspace")
    functional = next(row for row in document["sections"] if row["type"] == "functional_content")
    functional["id"] = fixture["public"]["sections"][0]["id"]
    document["sections"] = [functional]
    preview = pages.preview("makerspace", space.pk, actor=actor, version=0, document=document)
    assert json.loads(JSONRenderer().render(PreviewProjection(preview).data)) == fixture["preview"]
    state = pages.save("makerspace", space.pk, actor=actor, version=0, document=document)
    page = space.public_page
    page.published_revision = page.draft_revision
    page.save(update_fields=["published_revision"])
    live = PublicPageProjection(projection("makerspace", space, page)).data
    # The real revision token is generated by the service, rather than the fixture.
    expected = {**fixture["public"], "publication_token": str(state["draft_revision_id"])}
    assert json.loads(JSONRenderer().render(live)) == expected
    space.enabled_modules.remove("membership")
    space.save(update_fields=["enabled_modules"])
    assert all(link["family"] != "membership" for link in projection(
        "makerspace", space, page)["sections"][0]["payload"]["links"])


def test_render_fixtures_match_exact_serializers():
    fixtures = json.loads((Path(__file__).parent / "fixtures" / "review-r3.json").read_text())
    for fixture in fixtures.values():
        assert PublicPageProjection(fixture["public"]).data == fixture["public"]
        assert PreviewProjection(fixture["preview"]).data == fixture["preview"]
        section = fixture["public"]["sections"][0]
        assert PROJECTED_TYPES["functional_content"](section).data == section
