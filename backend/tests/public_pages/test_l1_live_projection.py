from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.test import APIRequestFactory
from apps.makerspaces import public_page_services as pages
from apps.makerspaces.models import Makerspace
from apps.makerspaces.public_page_access import resolve_handle
from apps.organizations.models import Organization, OrganizationMakerspace
from apps.organizations.public_catalog import public_events_for, linked_spaces_for, archive_card
from apps.events.models import EventOrganizer, Event
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)


def test_origin_and_host_both_constrain_tenant_resolution(page_owner, settings):
    owner, actor = page_owner
    settings.ALLOWED_HOSTS = ["testserver", ".example.test"]
    owner.frontend_domain, owner.frontend_domain_status = "a.example.test", "verified"
    owner.save(update_fields=["frontend_domain", "frontend_domain_status"])
    Makerspace.objects.create(name="B", slug="origin-b", frontend_domain="b.example.test", frontend_domain_status="verified")
    state = pages.change_handle("makerspace", owner.pk, actor=actor, version=0, handle="origin.lab")
    state = pages.save("makerspace", owner.pk, actor=actor, version=state["version"], document=state["document"])
    pages.publish("makerspace", owner.pk, actor=actor, version=state["version"], draft_revision_id=state["draft_revision_id"])
    factory = APIRequestFactory()
    assert resolve_handle("origin.lab", factory.get("/", HTTP_HOST="a.example.test", HTTP_ORIGIN="http://testserver"))
    for host, origin in (("testserver", "https://b.example.test"), ("b.example.test", "https://a.example.test"),
                         ("a.example.test", "https://unknown.example.test")):
        with pytest.raises(NotFound):
            resolve_handle("origin.lab", factory.get("/", HTTP_HOST=host, HTTP_ORIGIN=origin))


def test_p5_attribution_includes_unlinked_venues_and_archive_is_minimal():
    org = Organization.objects.create(name="Workshop organization", slug="workshop-org", public_profile_enabled=True)
    linked, remote = event_space("linked-host"), event_space("remote-host")
    OrganizationMakerspace.objects.create(organization=org, makerspace=linked, relationship="affiliate")
    own, elsewhere, unattributed = open_event(linked), open_event(remote), open_event(linked)
    EventOrganizer.objects.create(organization=org, event=own)
    EventOrganizer.objects.create(organization=org, event=elsewhere)
    upcoming = set(public_events_for(org).values_list("pk", flat=True))
    assert upcoming == {own.pk, elsewhere.pk} and unattributed.pk not in upcoming
    assert list(linked_spaces_for(org).values_list("pk", flat=True)) == [linked.pk]
    now = timezone.now()
    Event.objects.filter(pk=elsewhere.pk).update(starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1))
    past = public_events_for(org, period="past", now=now).get()
    card = archive_card(past)
    assert card["event_url"] is None and card["kind"] == "archive"
    assert set(card) == {"kind", "title", "description", "starts_at", "ends_at", "timezone", "event_url", "host"}
    remote.enabled_modules = []
    remote.save(update_fields=["enabled_modules"])
    assert not public_events_for(org, period="past", now=now).exists()
