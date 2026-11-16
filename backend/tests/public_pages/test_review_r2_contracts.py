"""Review-round-2 behavior and the exact payloads rendered by frontend regressions."""

from datetime import timedelta
import json
from pathlib import Path

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.events.models import Event, EventOrganizer
from apps.events.services_lifecycle import complete
from apps.events.serializers_website import PublicWebsiteSerializer
from apps.makerspaces import public_page_services as pages
from apps.makerspaces.public_page_projected_serializers import PROJECTED_TYPES
from apps.organizations.models import Organization
from apps.organizations.serializers_public import PublicOrganizationSerializer
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)


def public_org():
    return Organization.objects.create(name="Builders", slug="builders", public_profile_enabled=True)


def test_completed_event_stays_in_minimal_archive_and_respects_live_gates(settings):
    settings.PUBLIC_APP_BASE_URL = "http://testserver"
    settings.INFRA_HOSTS = ["testserver"]
    org = public_org()
    space = event_space("archive-host")  # No OrganizationMakerspace link is required.
    actor = make_staff(space)
    event = open_event(space)
    now = timezone.now()
    Event.objects.filter(pk=event.pk).update(starts_at=now - timedelta(hours=2), ends_at=now - timedelta(hours=1))
    event.refresh_from_db()
    EventOrganizer.objects.create(event=event, organization=org)
    complete(event, actor=actor)
    url = f"/api/v1/public/organizations/{org.slug}/events/"
    client = APIClient()
    response = client.get(url, {"period": "past"})
    assert response.status_code == 200
    assert response.data["count"] == 1
    card = response.data["results"][0]
    assert set(card) == {"kind", "title", "description", "starts_at", "ends_at", "timezone", "host", "event_url"}
    assert card["kind"] == "archive" and card["event_url"] is None
    assert client.get(url).data["count"] == 0
    for values in ({"status": "cancelled"}, {"status": "draft"}, {"status": "completed", "is_public": False}):
        Event.objects.filter(pk=event.pk).update(**values)
        assert client.get(url, {"period": "past"}).data["count"] == 0
    Event.objects.filter(pk=event.pk).update(status="completed", is_public=True)
    space.enabled_modules = []
    space.save(update_fields=["enabled_modules"])
    assert client.get(url, {"period": "past"}).data["count"] == 0
    space.enabled_modules = ["events"]
    space.save(update_fields=["enabled_modules"])
    assert client.get(url, {"period": "past"}).data["count"] == 1
    org.public_profile_enabled = False
    org.save(update_fields=["public_profile_enabled"])
    assert client.get(url, {"period": "past"}).status_code == 404


def test_legacy_organization_canonical_uses_platform_until_builder_is_published(page_owner, settings):
    settings.PUBLIC_APP_BASE_URL = "https://platform.example.test/"
    space, _ = page_owner
    space.frontend_domain, space.frontend_domain_status = "tenant.example.test", "verified"
    space.save(update_fields=["frontend_domain", "frontend_domain_status"])
    settings.ALLOWED_HOSTS = ["testserver", "tenant.example.test"]
    org = public_org()
    from apps.organizations.models import OrganizationMembership
    from apps.accounts.models import User
    governor = User.objects.create_user(username="org-governor", account_kind="member")
    OrganizationMembership.objects.create(organization=org, user=governor, governance_actions=["manage_organization_profile"])
    url = f"/api/v1/public/organizations/{org.slug}/"
    client = APIClient()
    response = client.get(url, HTTP_ORIGIN="https://tenant.example.test")
    assert response.status_code == 200
    assert response.data["canonical_url"] == "https://platform.example.test/o/builders"
    assert client.get(url + "page/").status_code == 404
    state = pages.change_handle("organization", org.pk, actor=governor, version=0, handle="builder.team")
    assert client.get(url).data["canonical_url"] == "https://platform.example.test/builder.team"
    state = pages.save("organization", org.pk, actor=governor, version=state["version"], document=state["document"])
    state = pages.publish("organization", org.pk, actor=governor, version=state["version"], draft_revision_id=state["draft_revision_id"])
    assert client.get(url).data["canonical_url"] == "https://platform.example.test/builder.team"
    pages.unpublish("organization", org.pk, actor=governor, version=state["version"])
    assert client.get(url).status_code == 404
    org.refresh_from_db()
    assert PublicOrganizationSerializer(org).data["canonical_url"] == "https://platform.example.test/o/builders"


def test_frontend_round_two_fixtures_are_exact_serializer_output(settings):
    rows = json.loads((Path(__file__).parent / "fixtures" / "review-r2.json").read_text())
    assert PublicWebsiteSerializer(rows["website"]).data == rows["website"]
    assert PROJECTED_TYPES["functional_content"](rows["functional"]).data == rows["functional"]
    settings.PUBLIC_APP_BASE_URL = "https://platform.example.test"
    org = public_org()
    org.description = "Build together"
    org.save(update_fields=["description"])
    assert PublicOrganizationSerializer(org).data == rows["legacy_organization"]
