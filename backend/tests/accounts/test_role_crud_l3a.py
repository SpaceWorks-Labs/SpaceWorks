from tests.accounts.account_factories import make_staff
from tests.accounts.reauth_helpers import force_recent_authenticate
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole


pytestmark = pytest.mark.django_db


def user(name, *, superadmin=False):
    creator = User.objects.create_superuser if superadmin else User.objects.create_user
    return creator(
        username=name,
        password="password",
        access_status=User.AccessStatus.ACTIVE,
        role=User.Role.SUPERADMIN if superadmin else User.Role.REQUESTER,
        is_superuser=superadmin,
        account_kind="platform" if superadmin else "member",
    )


def space(slug, **kwargs):
    return Makerspace.objects.create(name=slug, slug=slug, **kwargs)


def client(actor):
    value = APIClient()
    force_recent_authenticate(value, actor)
    return value


def list_url(makerspace):
    return reverse("admin-role-list-create", kwargs={"makerspace_id": makerspace.id})


def test_catalogue_lists_seven_fixed_roles_and_assignment_flags():
    makerspace = space("roles")
    actor = make_staff(makerspace, username="roles-manager", password="password")
    response = client(actor).get(list_url(makerspace))
    assert response.status_code == 200
    assert [row["slug"] for row in response.data] == [
        "space_manager", "inventory_manager", "machine_manager", "event_manager",
        "booking_manager", "handover", "member",
    ]
    for row in response.data:
        assert row["is_default"] and row["is_protected"]
        assert row["exclusive"] is (row["slug"] in {"space_manager", "member"})
        assert row["combinable"] is (row["slug"] not in {"space_manager", "member"})


def test_role_listing_refuses_foreign_spaces():
    makerspace = space("role-list-scope")
    actor = make_staff(makerspace, username="role-list-manager", password="password")
    other = space("role-list-foreign")
    assert client(actor).get(list_url(other)).status_code == 404
    assert client(user("outsider")).get(list_url(makerspace)).status_code == 404
