"""Organization catalogues hide a disabled host's events and restore the same rows."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.events.models import Event, EventOrganizer
from apps.makerspaces.module_install import install_module, uninstall_module
from tests.organizations.test_public_directory import event, host, organization


@pytest.mark.django_db
def test_organization_event_catalogue_off_on_restores_rows_and_exact_payload():
    org = organization()
    space = host("area-org-events")
    scheduled = event(space, "Retained organization workshop")
    link = EventOrganizer.objects.create(event=scheduled, organization=org)
    before_event = Event.objects.filter(pk=scheduled.pk).values().get()
    before_link = EventOrganizer.objects.filter(pk=link.pk).values().get()
    url = reverse("public-organization-events", kwargs={"slug": org.slug})
    client = APIClient()

    on = client.get(url)
    assert on.status_code == 200
    assert on.data["count"] == 1
    assert on.data["results"][0]["title"] == "Retained organization workshop"

    assert uninstall_module(space, "events") == ["events"]
    off = client.get(url)
    assert off.status_code == 200
    assert off.data["count"] == 0
    assert off.data["results"] == []
    assert Event.objects.filter(pk=scheduled.pk).values().get() == before_event
    assert EventOrganizer.objects.filter(pk=link.pk).values().get() == before_link

    assert install_module(space, "events") == ["events"]
    restored = client.get(url)
    assert restored.status_code == 200
    assert restored.data == on.data
    assert Event.objects.filter(pk=scheduled.pk).values().get() == before_event
    assert EventOrganizer.objects.filter(pk=link.pk).values().get() == before_link
