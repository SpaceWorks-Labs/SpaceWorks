"""Exercise rendered response contracts and generated discriminators together."""
from uuid import uuid4
import pytest
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from apps.events.serializers_website import WebsiteSerializer, PublicWebsiteSerializer
from apps.events.views_website_admin import EventWebsiteView
from apps.events.views_website_public import PublicEventWebsiteView
from apps.events.services_website import save_content, set_release
from apps.events.website_projection import project
from apps.makerspaces.public_page_editor_views import PageEditorView
from apps.makerspaces.public_page_views import PublicPageView
from apps.makerspaces.public_page_projected_serializers import ProjectedSections
from apps.makerspaces.public_page_serializers import EditorState
from apps.makerspaces import public_page_services as pages
from tests.events.website_helpers import session

pytestmark = pytest.mark.django_db(transaction=True)


def test_public_projected_team_and_gallery_strip_editor_identifiers():
    rows = [{"id": str(uuid4()), "type": "team", "enabled": True, "payload": {"title": "Team", "entries": [
        {"id": str(uuid4()), "kind": "member", "display_name": "Maker", "role": "Teacher", "handle": "maker.lab",
         "url": "https://example.test/maker.lab", "avatar_url": None, "profile_id": 123}]}},
        {"id": str(uuid4()), "type": "gallery", "enabled": True, "payload": {"title": "Gallery", "items": [
            {"url": "/private-image/", "alt": "Workshop", "caption": "", "asset_id": 12}]}}]
    data = ProjectedSections().to_representation(rows)
    assert "profile_id" not in data[0]["payload"]["entries"][0]
    assert "asset_id" not in data[1]["payload"]["items"][0]
    assert data[0]["payload"]["entries"][0]["handle"] == "maker.lab"


def test_event_public_schema_and_output_omit_editor_state(event_owner):
    _, actor, event = event_owner
    save_content(event, actor=actor, data={"revision": 0, "sections": [], "sessions": [session(event)]})
    set_release(event, actor=actor, released=True, revision=project(event)["revision"])
    editorial = project(event)
    editorial["capabilities"] = {"can_edit_details": True, "can_publish_schedule": True}
    assert WebsiteSerializer(editorial).data["delay_targets"][0]["working_present"]
    public = project(event, public=True)
    public.update({key: editorial[key] for key in ("capabilities", "delay_targets", "draft_revision_id", "published_revision_id")})
    data = PublicWebsiteSerializer(public).data
    assert not {"capabilities", "delay_targets", "draft_revision_id", "published_revision_id", "assets"} & data.keys()
    assert data["editorial_document"]["cover_asset_id"] is None


def test_editor_state_serializes_typed_capabilities_without_changing_envelope(page_owner):
    space, actor = page_owner
    state = pages.read_editor("makerspace", space.pk, actor=actor)
    actual = EditorState(state).data
    assert set(actual) == set(state)
    assert actual["limits"] == state["limits"]
    assert set(actual["capabilities"]) == set(state["capabilities"])


def test_openapi_documents_projected_and_event_unions_without_generic_payloads():
    patterns = [path("editor/<int:pk>/", PageEditorView.as_view()),
        path("page/<slug:makerspace_slug>/", PublicPageView.as_view()),
        path("event/<int:pk>/", EventWebsiteView.as_view()),
        path("public/<slug:makerspace_slug>/<uuid:public_token>/", PublicEventWebsiteView.as_view())]
    schema = SchemaGenerator(patterns=patterns).get_schema(public=True)
    components = schema["components"]["schemas"]
    public = components["ProjectedPublicPageSection"]
    assert set(public["discriminator"]["mapping"]) == {
        "about", "gallery", "team", "testimonials", "links", "stats", "location", "upcoming_events",
        "linked_makerspaces", "organization_events", "functional_content",
        # 0.12.0 sections: membership plans, sponsors, shop and crew (`PUBLIC_PAYLOADS`).
        "membership_plans", "sponsors", "shop", "crew"}
    # Release 2 (#128 C-36): an event page also carries the opt-in public crew section.
    assert set(components["EventEditorialSectionInput"]["discriminator"]["mapping"]) == {
        "about", "gallery", "team", "testimonials", "links", "crew"}
    for key in ("capabilities", "delay_targets", "draft_revision_id", "published_revision_id"):
        assert key not in components["PublicWebsite"]["properties"]
    assert "$ref" in components["Website"]["properties"]["capabilities"]
