"""Ownerless spaces stay usable; seed_e2e and /control/ races are the edges of the rule."""
import json

import pytest
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.organizations import services_owner
from apps.organizations.models import Organization, OrganizationMakerspace
from apps.organizations.services_console import OrganizationConflict
from tests.makerspaces.space_pack_helpers import client, person, space
from tests.makerspaces.test_control_makerspace_admin import control_client, form_payload

pytestmark = pytest.mark.django_db
BASE = "/api/v1/admin/makerspaces"


def test_ownerless_space_is_listed_and_editable_by_its_staff_and_superadmin():
    row, manager = space("ownerless-lab")
    assert not OrganizationMakerspace.objects.filter(makerspace=row).exists()
    listed = client(manager).get(BASE)
    assert listed.status_code == 200 and row.pk in {item["id"] for item in listed.data}
    response = client(manager).patch(f"{BASE}/{row.pk}", {"location": "Hall C"}, format="json")
    assert response.status_code == 200, response.data
    root = person("ownerless-root", superadmin=True)
    response = client(root).patch(f"{BASE}/{row.pk}", {"name": "Renamed Lab"}, format="json")
    assert response.status_code == 200, response.data
    row.refresh_from_db()
    assert (row.name, row.location) == ("Renamed Lab", "Hall C")
    assert not OrganizationMakerspace.objects.exists() and not Organization.objects.exists()


def test_seed_e2e_may_create_an_ownerless_space(settings, tmp_path, monkeypatch):
    settings.DEBUG = True
    settings.EVENT_STATION_PIN_PEPPER = "test-only-independent-station-pepper"
    monkeypatch.delenv("E2E_SEED_ALLOWED", raising=False)
    out = tmp_path / "seed.json"
    call_command("seed_e2e", "--write-json", str(out), "--password", "pw-for-test")
    seeded = Makerspace.objects.get(slug=json.loads(out.read_text())["slug"])
    assert not OrganizationMakerspace.objects.filter(makerspace=seeded).exists()
    assert not AuditLog.objects.filter(action="organization.created").exists()


def test_control_owner_failure_after_validation_rolls_back_with_a_message(monkeypatch):
    def refuse(*args, **kwargs):
        raise OrganizationConflict("This makerspace already has an owner organization.")

    monkeypatch.setattr(services_owner, "assign_owner_organization", refuse)
    candidate = Makerspace(name="Raced Control", slug="raced-control", public_code="RACE")
    url = reverse("admin:makerspaces_makerspace_add")
    response = control_client().post(url, form_payload(candidate, new_organization_name="Raced Owner"))
    assert response.status_code == 302 and response.url == url
    notes = [str(message) for message in get_messages(response.wsgi_request)]
    assert notes == ["Makerspace was not created: This makerspace already has an owner organization."]
    assert not Makerspace.objects.filter(slug="raced-control").exists()
    assert not Organization.objects.exists() and not OrganizationMakerspace.objects.exists()
    assert not AuditLog.objects.filter(action="makerspace.created").exists()
