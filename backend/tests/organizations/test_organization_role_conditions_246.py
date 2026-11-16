"""Decision 246: organization administration across every built-in space role, anonymous callers and the superadmin.

Creating an organization and linking it to a space is platform-only. A space role (whatever it holds in a
space) never creates, links or unlinks, and never sees an organization it has no stake in. The superadmin
path is idempotent (re-linking updates, it does not duplicate) and validated, and every write is audited.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.role_catalog import ROLE_CATALOG
from apps.organizations.models import Organization, OrganizationMakerspace
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.fixed_roles.helpers import staff_account
from tests.organizations.test_org_authority import make_makerspace, make_organization, make_user

pytestmark = pytest.mark.django_db
BASE = "/api/v1/admin/organizations/"
SLUGS = [role.slug for role in ROLE_CATALOG]


def _client(user=None):
    client = APIClient()
    if user is not None:
        force_recent_authenticate(client, user)
    return client


def _super(name="org246-super"):
    return make_user(name, role=User.Role.SUPERADMIN)


@pytest.mark.parametrize("slug", SLUGS)
def test_no_built_in_space_role_creates_links_or_unlinks_an_organization(slug):
    space = make_makerspace(f"o246-{slug}".replace("_", "-"))
    org = make_organization(f"o246-org-{slug}".replace("_", "-"))
    actor = _client(staff_account(space, f"o246-actor-{slug}", slug))
    created = actor.post(BASE, {"name": "Rogue", "slug": f"rogue-{slug}".replace("_", "-")}, format="json")
    linked = actor.post(f"{BASE}{org.pk}/makerspaces/", {"makerspace_id": space.pk, "relationship": "affiliate"},
                        format="json")
    unlinked = actor.delete(f"{BASE}{org.pk}/makerspaces/{space.pk}/")
    for refused in (created, linked, unlinked):
        assert refused.status_code in (403, 404), refused.content
    assert not Organization.objects.filter(name="Rogue").exists()
    assert not OrganizationMakerspace.objects.filter(organization=org).exists()
    assert not AuditLog.objects.filter(action__startswith="organization.", actor__username=f"o246-actor-{slug}").exists()


@pytest.mark.parametrize("slug", SLUGS)
def test_a_space_role_never_sees_an_organization_it_has_no_membership_in(slug):
    space = make_makerspace(f"o246v-{slug}".replace("_", "-"))
    hidden = make_organization(f"o246v-org-{slug}".replace("_", "-"))
    actor = _client(staff_account(space, f"o246v-actor-{slug}", slug))
    listed = actor.get(BASE)
    assert listed.status_code in (200, 403, 404)
    if listed.status_code == 200:
        assert hidden.pk not in [row["id"] for row in listed.json()["results"]]
    assert actor.get(f"{BASE}{hidden.pk}/").status_code in (403, 404)
    assert actor.patch(f"{BASE}{hidden.pk}/", {"name": "Taken"}, format="json").status_code in (403, 404)
    hidden.refresh_from_db()
    assert hidden.name != "Taken"


def test_anonymous_is_refused_on_every_organization_admin_route():
    org = make_organization("o246-anon")
    space = make_makerspace("o246-anon-space")
    anon = _client()
    assert anon.get(BASE).status_code in (401, 403)
    assert anon.post(BASE, {"name": "x", "slug": "x"}, format="json").status_code in (401, 403)
    assert anon.get(f"{BASE}{org.pk}/").status_code in (401, 403)
    assert anon.post(f"{BASE}{org.pk}/makerspaces/", {"makerspace_id": space.pk, "relationship": "affiliate"},
                     format="json").status_code in (401, 403)


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "No slug"}, {"slug": "no-name"},
                                  {"name": "Bad slug", "slug": "Has Spaces!"}])
def test_create_validation_rejects_missing_or_malformed_fields(body):
    response = _client(_super()).post(BASE, body, format="json")
    assert response.status_code == 400
    assert not Organization.objects.exists()


def test_a_duplicate_slug_is_a_400_and_one_organization_stands():
    boss = _client(_super())
    body = {"name": "Network", "slug": "network-246"}
    assert boss.post(BASE, body, format="json").status_code == 201
    assert boss.post(BASE, body, format="json").status_code == 400
    assert Organization.objects.filter(slug="network-246").count() == 1
    assert AuditLog.objects.filter(action="organization.created").count() == 1


@pytest.mark.parametrize("payload", [{}, {"makerspace_id": 99999999, "relationship": "affiliate"},
                                     {"relationship": "affiliate"}, {"makerspace_id": 1, "relationship": "overlord"}])
def test_link_validation_rejects_unknown_space_missing_id_and_bad_relationship(payload):
    org = make_organization("o246-linkval")
    response = _client(_super()).post(f"{BASE}{org.pk}/makerspaces/", payload, format="json")
    assert response.status_code in (400, 404)
    assert not OrganizationMakerspace.objects.filter(organization=org).exists()


def test_linking_twice_updates_the_one_link_and_unlinking_twice_is_404():
    boss = _client(_super())
    org = make_organization("o246-idem")
    space = make_makerspace("o246-idem-space")
    url = f"{BASE}{org.pk}/makerspaces/"
    assert boss.post(url, {"makerspace_id": space.pk, "relationship": "affiliate"}, format="json").status_code == 200
    assert boss.post(url, {"makerspace_id": space.pk, "relationship": "affiliate"}, format="json").status_code == 200
    assert OrganizationMakerspace.objects.filter(organization=org, makerspace=space).count() == 1
    assert boss.delete(f"{url}{space.pk}/").status_code == 204
    assert boss.delete(f"{url}{space.pk}/").status_code == 404


def test_unknown_organization_ids_are_404_for_the_superadmin():
    boss = _client(_super())
    assert boss.get(f"{BASE}99999999/").status_code == 404
    assert boss.post(f"{BASE}99999999/makerspaces/", {"makerspace_id": 1, "relationship": "affiliate"},
                     format="json").status_code == 404
