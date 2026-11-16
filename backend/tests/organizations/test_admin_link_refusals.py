"""Admin forms report link policy refusals, including transactional rechecks."""

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.organizations import admin_links
from apps.organizations.models import Organization, OrganizationMakerspace
from tests.accounts.reauth_helpers import force_recent_control_login

pytestmark = pytest.mark.django_db


@pytest.fixture
def link_editor(client):
    root = User.objects.create_superuser(username="link-editor", password="pw")
    force_recent_control_login(client, root)
    organization = Organization.objects.create(name="Link organization", slug="link-organization")
    space = Makerspace.objects.create(name="Link venue", slug="link-venue")
    return client, organization, space


@pytest.mark.parametrize("change", [False, True])
def test_inactive_organization_is_a_bound_admin_form_error(link_editor, change):
    client, organization, space = link_editor
    row = OrganizationMakerspace.objects.create(
        organization=organization, makerspace=space, relationship="affiliate",
    ) if change else None
    organization.is_active = False
    organization.save(update_fields=["is_active"])
    url = reverse("admin:organizations_organizationmakerspace_change", args=[row.pk]) if change else reverse(
        "admin:organizations_organizationmakerspace_add")
    response = client.post(url, {"organization": organization.pk, "makerspace": space.pk, "relationship": "owner"})
    assert response.status_code == 200
    form = response.context["adminform"].form
    assert form.is_bound
    assert "Reactivate the organization" in str(form.non_field_errors())
    if row:
        row.refresh_from_db()
        assert row.relationship == "affiliate"
    else:
        assert not OrganizationMakerspace.objects.exists()
    assert not AuditLog.objects.filter(action__startswith="organization.link_").exists()


@pytest.mark.parametrize("change", [False, True])
def test_service_recheck_refusal_rolls_back_and_renders_bound_form(link_editor, monkeypatch, change):
    client, organization, space = link_editor
    row = OrganizationMakerspace.objects.create(
        organization=organization, makerspace=space, relationship="affiliate",
    ) if change else None
    original = admin_links.change_link
    calls = []

    def deactivate_before_locked_recheck(*args, **kwargs):
        calls.append(True)
        Organization.objects.filter(pk=organization.pk).update(is_active=False)
        return original(*args, **kwargs)

    monkeypatch.setattr(admin_links, "change_link", deactivate_before_locked_recheck)
    url = reverse("admin:organizations_organizationmakerspace_change", args=[row.pk]) if change else reverse(
        "admin:organizations_organizationmakerspace_add")
    response = client.post(url, {"organization": organization.pk, "makerspace": space.pk, "relationship": "owner"})
    assert response.status_code == 200
    form = response.context["adminform"].form
    assert form.is_bound and form.data["relationship"] == "owner"
    assert "Reactivate the organization" in str(form.non_field_errors())
    assert calls == [True]  # Rendering the error must never try the mutation again.
    organization.refresh_from_db()
    assert organization.is_active  # The failed admin POST transaction was rolled back.
    if row:
        row.refresh_from_db()
        assert row.relationship == "affiliate"
    else:
        assert not OrganizationMakerspace.objects.exists()
    assert not AuditLog.objects.filter(action__startswith="organization.link_").exists()


def test_valid_link_still_uses_service_and_records_audit(link_editor):
    client, organization, space = link_editor
    response = client.post(reverse("admin:organizations_organizationmakerspace_add"), {
        "organization": organization.pk, "makerspace": space.pk, "relationship": "owner",
    })
    assert response.status_code == 302
    row = OrganizationMakerspace.objects.get(organization=organization, makerspace=space)
    assert row.relationship == "owner"
    assert AuditLog.objects.filter(action="organization.link_created", target_id=str(row.pk)).exists()
