"""The makerspace create boundary requires exactly one active owner choice."""
import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMakerspace
from tests.makerspaces.space_pack_helpers import client, person, space
from tests.organizations.test_org_authority import make_organization

pytestmark = pytest.mark.django_db
BASE = "/api/v1/admin/makerspaces"


def payload(**choices):
    return {"name": "Owner Lab", "slug": "owner-api-lab", "public_code": "OWNR", **choices}


@pytest.mark.parametrize("existing", [False, True])
def test_create_assigns_existing_or_new_owner_in_same_transaction(existing):
    actor = person("owner-api-root", superadmin=True)
    org = make_organization("owner-existing") if existing else None
    choices = {"organization_id": org.pk} if org else {"organization_name": "New Owner"}
    response = client(actor).post(BASE, payload(**choices), format="json")
    assert response.status_code == 201, response.data
    row = OrganizationMakerspace.objects.get(makerspace_id=response.data["id"])
    assert row.relationship == "owner" and row.created_by == actor
    assert row.organization == org if existing else row.organization.name == "New Owner"
    assert Organization.objects.count() == 1
    assert "organization_id" not in response.data and "organization_name" not in response.data
    assert AuditLog.objects.filter(makerspace=row.makerspace, action="organization.link_created").exists()


@pytest.mark.parametrize("both", [False, True])
def test_create_requires_exactly_one_choice_with_both_field_errors(both):
    actor = person("owner-api-choice", superadmin=True)
    choices = {"organization_id": make_organization("owner-choice").pk, "organization_name": "Other"} if both else {}
    before = Organization.objects.count()
    response = client(actor).post(BASE, payload(**choices), format="json")
    assert response.status_code == 400, response.data
    assert {"organization_id", "organization_name"} <= set(response.data)
    assert not Makerspace.objects.exists() and not OrganizationMakerspace.objects.exists()
    assert Organization.objects.count() == before


def test_inactive_organization_rolls_back_makerspace_and_audits():
    actor = person("owner-api-inactive", superadmin=True)
    org = make_organization("owner-inactive", is_active=False)
    before = AuditLog.objects.count()
    response = client(actor).post(BASE, payload(organization_id=org.pk), format="json")
    assert response.status_code == 400 and "organization_id" in response.data
    assert not Makerspace.objects.exists() and not OrganizationMakerspace.objects.exists()
    assert Organization.objects.count() == 1 and AuditLog.objects.count() == before


def test_staff_invalid_body_is_forbidden_before_serializer_validation():
    _, actor = space("owner-api-staff")
    before = Makerspace.objects.count()
    response = client(actor).post(BASE, {"organization_id": "invalid"}, format="json")
    assert response.status_code == 403, response.data
    assert Makerspace.objects.count() == before and not Organization.objects.exists()


@pytest.mark.parametrize("choices", [
    {"organization_id": 1}, {"organization_name": "Replacement"},
    {"organization_id": 1, "organization_name": "Replacement"},
])
def test_patch_refuses_owner_fields_without_updating_other_fields(choices):
    row, _ = space("owner-api-patch")
    actor = person("owner-api-patch-root", superadmin=True)
    before = AuditLog.objects.count()
    response = client(actor).patch(f"{BASE}/{row.pk}", {"name": "Changed", **choices}, format="json")
    assert response.status_code == 400, response.data
    assert set(choices) <= set(response.data)
    row.refresh_from_db()
    assert row.name == "owner-api-patch"
    assert not OrganizationMakerspace.objects.exists() and not Organization.objects.exists()
    assert AuditLog.objects.count() == before


def test_unknown_install_profile_with_valid_org_returns_404_and_creates_nothing():
    actor = person("owner-api-profile", superadmin=True)
    org = make_organization("owner-profile")
    before = AuditLog.objects.count()
    response = client(actor).post(BASE, payload(organization_id=org.pk, install_profile_id=987654321), format="json")
    assert response.status_code == 404, response.data
    assert not Makerspace.objects.exists() and not OrganizationMakerspace.objects.exists()
    assert Organization.objects.count() == 1 and AuditLog.objects.count() == before
