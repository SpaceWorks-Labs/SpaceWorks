"""Owner assignment shares console authorization, freeze and audit guarantees."""
import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.organizations.models import Organization, OrganizationMakerspace
from apps.organizations.services_console import OrganizationConflict
from apps.organizations.services_owner import assign_owner_organization, organization_slug
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from tests.organizations.test_admin_create_link import superadmin
from tests.organizations.test_org_authority import make_makerspace, make_organization, make_user
from tests.tenant_migration.source_gate_helpers import close_gate

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("name", ["", "工具", "   "])
def test_empty_or_non_ascii_slug_falls_back_to_organization(name):
    assert organization_slug(name, taken=lambda _: False) == "organization"


def test_slug_collisions_allocate_numbered_suffixes():
    taken = set()
    for expected in ("network", "network-2", "network-3"):
        slug = organization_slug("Network", taken=taken.__contains__)
        assert slug == expected
        taken.add(slug)


def test_long_slug_including_large_collision_suffix_fits_model_limit():
    candidates = []

    def taken(slug):
        candidates.append(slug)
        return len(candidates) < 100001

    slug = organization_slug("a" * 200, taken=taken)
    assert slug.endswith("-100001")
    assert max(map(len, candidates)) <= 50


def test_new_name_creates_owner_and_console_shaped_audits():
    actor, space = superadmin(), make_makerspace("owner-new")
    row = assign_owner_organization(actor, space.pk, new_name="  Community Network  ")
    assert row.makerspace == space and row.created_by == actor
    assert row.relationship == "owner"
    org = row.organization
    assert org.name == "Community Network" and org.slug == "community-network"
    assert org.created_by == actor
    created = AuditLog.objects.get(action="organization.created", target_id=str(org.pk))
    assert created.actor == actor and created.makerspace_id is None
    assert created.meta == {"fields": ["name", "slug"]}
    linked = AuditLog.objects.get(action="organization.link_created", target_id=str(row.pk))
    assert linked.actor == actor and linked.makerspace == space
    assert linked.meta == {"organization_id": org.pk, "relationship": "owner"}


def test_existing_active_organization_is_linked_without_creating_another():
    actor, space, org = superadmin(), make_makerspace("owner-existing"), make_organization("existing")
    row = assign_owner_organization(actor, space.pk, organization_id=org.pk)
    assert row.organization == org and row.relationship == "owner"
    assert Organization.objects.count() == 1
    assert not AuditLog.objects.filter(action="organization.created").exists()
    assert AuditLog.objects.get(action="organization.link_created").meta == {
        "organization_id": org.pk, "relationship": "owner",
    }


@pytest.mark.parametrize("inactive", [False, True])
def test_unknown_or_inactive_organization_is_a_field_error(inactive):
    actor, space = superadmin(), make_makerspace("owner-invalid")
    org_id = make_organization("inactive", is_active=False).pk if inactive else 987654321
    with pytest.raises(ValidationError) as caught:
        assign_owner_organization(actor, space.pk, organization_id=org_id)
    assert set(caught.value.detail) == {"organization_id"}
    assert not OrganizationMakerspace.objects.exists()
    assert not AuditLog.objects.filter(action__startswith="organization.").exists()


@pytest.mark.parametrize("choices", [{}, {"organization_id": 1, "new_name": "Network"}])
def test_exactly_one_owner_choice_is_required(choices):
    actor, space = superadmin(), make_makerspace("owner-choice")
    with pytest.raises(ValidationError) as caught:
        assign_owner_organization(actor, space.pk, **choices)
    assert set(caught.value.detail) == {"organization_id", "organization_name"}
    assert not Organization.objects.exists() and not OrganizationMakerspace.objects.exists()


def test_already_owned_space_refuses_without_creating_a_second_organization():
    actor, space = superadmin(), make_makerspace("owner-conflict")
    original = assign_owner_organization(actor, space.pk, new_name="Original")
    before = AuditLog.objects.count()
    with pytest.raises(OrganizationConflict):
        assign_owner_organization(actor, space.pk, new_name="Replacement")
    assert OrganizationMakerspace.objects.get(makerspace=space) == original
    assert Organization.objects.count() == 1 and AuditLog.objects.count() == before


def test_non_superadmin_cannot_assign_an_owner():
    actor, space = make_user("owner-denied"), make_makerspace("owner-denied")
    with pytest.raises(PermissionDenied):
        assign_owner_organization(actor, space.pk, new_name="Denied")
    assert not Organization.objects.exists() and not OrganizationMakerspace.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_frozen_space_refuses_before_creating_organization_link_or_audit():
    actor, space = superadmin(), make_makerspace("owner-frozen")
    close_gate(space, actor)
    before = AuditLog.objects.count()
    with pytest.raises(SourceMigrationGateClosed):
        assign_owner_organization(actor, space.pk, new_name="Frozen")
    assert not Organization.objects.exists() and not OrganizationMakerspace.objects.exists()
    assert AuditLog.objects.count() == before
