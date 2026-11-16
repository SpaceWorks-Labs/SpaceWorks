"""The analytics login route checks module, permission and scope BEFORE any database-role DDL (SWITCH-MATRIX).

`POST .../analytics/login` issues `CREATE ROLE` through `provisioning.ensure_login`. A refused caller must never get
that far: authority is decided first, then a literal JSON confirm=true is required before provisioning.
The DDL seam is replaced by a recorder, so these tests assert exact refusals AND that nothing was provisioned.
"""

import pytest
from django.urls import reverse
from django.db import connection

from apps.analytics import provisioning
from apps.makerspaces.module_install import uninstall_module
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


@pytest.fixture
def ddl(monkeypatch):
    calls = []
    monkeypatch.setattr(provisioning, "ensure_login", lambda role, password, makerspace_id, using="default": calls.append(role))
    monkeypatch.setattr(provisioning, "drop_login", lambda role, using="default": calls.append(role))
    monkeypatch.setattr(provisioning, "availability", lambda: (True, ""))
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolname FROM pg_roles ORDER BY rolname")
        before = cursor.fetchall()
    yield calls
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolname FROM pg_roles ORDER BY rolname")
        assert cursor.fetchall() == before


def _url(space, name="admin-makerspace-analytics-login"):
    return reverse(name, args=[space.pk])


def test_a_member_is_refused_403_and_no_role_is_created(ddl):
    space = make_space("sw-an-member")
    member = make_member("sw-an-member-user", space, membership_role="custom", role="requester")
    response = authenticated_client(member).post(_url(space), {"confirm": True}, format="json")
    assert (response.status_code, response.data["code"]) == (403, "permission_denied")
    assert ddl == []


def test_a_non_manager_staff_member_is_refused_403_and_no_role_is_created(ddl):
    space = make_space("sw-an-staff")
    staff = staff_account(space, "sw-an-staff-user", "inventory_manager")
    response = authenticated_client(staff).post(_url(space), {"confirm": True}, format="json")
    assert (response.status_code, response.data["code"]) == (403, "permission_denied")
    assert ddl == []


def test_a_space_manager_of_another_space_is_refused_and_no_role_is_created(ddl):
    space, other = make_space("sw-an-home"), make_space("sw-an-away")
    outsider = staff_account(other, "sw-an-outsider", "space_manager")
    response = authenticated_client(outsider).post(_url(space), {"confirm": True}, format="json")
    assert (response.status_code, response.data["code"]) == (404, "not_found")
    assert ddl == []


def test_the_platform_route_is_refused_to_a_space_manager_and_no_role_is_created(ddl):
    space = make_space("sw-an-platform")
    manager = staff_account(space, "sw-an-platform-user", "space_manager")
    response = authenticated_client(manager).post(reverse("admin-platform-analytics-login"), {"confirm": True}, format="json")
    assert (response.status_code, response.data["code"]) == (403, "permission_denied")
    assert ddl == []


def test_analytics_off_answers_404_module_disabled_before_any_permission_or_ddl(ddl):
    space = make_space("sw-an-off")
    manager = staff_account(space, "sw-an-off-user", "space_manager")
    uninstall_module(space, "analytics")
    response = authenticated_client(manager).post(_url(space), {"confirm": True}, format="json")
    assert (response.status_code, response.data["code"], response.data["module"]) == (404, "module_disabled", "analytics")
    assert ddl == []


def test_the_space_manager_reaches_the_ddl_exactly_once(ddl):
    space = make_space("sw-an-ok")
    manager = staff_account(space, "sw-an-ok-user", "space_manager")
    response = authenticated_client(manager).post(_url(space), {"confirm": True}, format="json")
    assert response.status_code == 201, response.data
    assert len(ddl) == 1


@pytest.mark.parametrize("body", [{}, {"confirm": False}, {"confirm": "invalid"}, {"confirm": 1},
                                 {"confirm": True, "role": "postgres"}, [], None])
def test_invalid_input_is_typed_400_before_any_ddl_or_connection_write(ddl, body):
    from apps.analytics.models import AnalyticsConnection
    from apps.audit.models import AuditLog
    space = make_space("sw-an-invalid")
    manager = staff_account(space, "sw-an-invalid-user", "space_manager")
    before = AuditLog.objects.count()
    response = authenticated_client(manager).post(_url(space), body, format="json")
    assert (response.status_code, response.data["code"]) == (400, "invalid")
    assert ddl == []
    assert not AnalyticsConnection.objects.filter(makerspace=space).exists()
    assert AuditLog.objects.count() == before


@pytest.mark.parametrize("operation", ["rotate", "revoke"])
def test_rotate_and_revoke_require_an_existing_login_before_any_ddl(ddl, operation):
    space = make_space("sw-an-existing")
    manager = staff_account(space, "sw-an-existing-manager", "space_manager")
    client = authenticated_client(manager)
    response = (client.post(_url(space, "admin-makerspace-analytics-login-rotate")) if operation == "rotate"
                else client.delete(_url(space)))
    assert (response.status_code, response.data["code"]) == (409, "analytics_login_missing")
    assert ddl == []


@pytest.mark.parametrize("operation", ["rotate", "revoke"])
@pytest.mark.parametrize("foreign", [False, True])
def test_rotate_and_revoke_refuse_missing_authority_before_any_ddl(ddl, operation, foreign):
    space = make_space("sw-an-authority")
    home = make_space("sw-an-foreign") if foreign else space
    actor = staff_account(home, "sw-an-authority-user", "space_manager" if foreign else "inventory_manager")
    client = authenticated_client(actor)
    response = (client.post(_url(space, "admin-makerspace-analytics-login-rotate")) if operation == "rotate"
                else client.delete(_url(space)))
    assert (response.status_code, response.data["code"]) == ((404, "not_found") if foreign else (403, "permission_denied"))
    assert ddl == []
