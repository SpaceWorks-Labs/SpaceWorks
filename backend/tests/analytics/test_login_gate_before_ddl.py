"""The analytics login route checks module, permission and scope BEFORE any database-role DDL (SWITCH-MATRIX).

`POST .../analytics/login` issues `CREATE ROLE` through `provisioning.ensure_login`. A refused caller must never get
that far: the route takes no body, so the only inputs are who calls and which space, and both are decided first.
The DDL seam is replaced by a recorder, so these tests assert exact refusals AND that nothing was provisioned.
"""

import pytest
from django.urls import reverse

from apps.analytics import provisioning
from apps.makerspaces.module_install import uninstall_module
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


@pytest.fixture
def ddl(monkeypatch):
    calls = []
    monkeypatch.setattr(provisioning, "ensure_login", lambda role, password, makerspace_id, using="default": calls.append(role))
    monkeypatch.setattr(provisioning, "availability", lambda: (True, ""))
    return calls


def _url(space, name="admin-makerspace-analytics-login"):
    return reverse(name, args=[space.pk])


def test_a_member_is_refused_403_and_no_role_is_created(ddl):
    space = make_space("sw-an-member")
    member = make_member("sw-an-member-user", space, membership_role="custom", role="requester")
    response = authenticated_client(member).post(_url(space))
    assert response.status_code in (403, 404), response.status_code
    assert ddl == []


def test_a_non_manager_staff_member_is_refused_403_and_no_role_is_created(ddl):
    space = make_space("sw-an-staff")
    staff = staff_account(space, "sw-an-staff-user", "inventory_manager")
    response = authenticated_client(staff).post(_url(space))
    assert response.status_code == 403
    assert ddl == []


def test_a_space_manager_of_another_space_is_refused_and_no_role_is_created(ddl):
    space, other = make_space("sw-an-home"), make_space("sw-an-away")
    outsider = staff_account(other, "sw-an-outsider", "space_manager")
    response = authenticated_client(outsider).post(_url(space))
    assert response.status_code in (403, 404)
    assert ddl == []


def test_the_platform_route_is_refused_to_a_space_manager_and_no_role_is_created(ddl):
    space = make_space("sw-an-platform")
    manager = staff_account(space, "sw-an-platform-user", "space_manager")
    response = authenticated_client(manager).post(reverse("admin-platform-analytics-login"))
    assert response.status_code == 403
    assert ddl == []


def test_analytics_off_answers_404_module_disabled_before_any_permission_or_ddl(ddl):
    space = make_space("sw-an-off")
    manager = staff_account(space, "sw-an-off-user", "space_manager")
    uninstall_module(space, "analytics")
    response = authenticated_client(manager).post(_url(space))
    assert (response.status_code, response.data["code"], response.data["module"]) == (404, "module_disabled", "analytics")
    assert ddl == []


def test_the_space_manager_reaches_the_ddl_exactly_once(ddl):
    space = make_space("sw-an-ok")
    manager = staff_account(space, "sw-an-ok-user", "space_manager")
    response = authenticated_client(manager).post(_url(space))
    assert response.status_code == 201, response.data
    assert len(ddl) == 1
