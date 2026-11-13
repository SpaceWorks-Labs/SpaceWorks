"""Open item C13: module defaults and the platform admin list (superadmin only, admin list audited)."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


def _root(username="c13-root"):
    from apps.accounts.models import User

    return User.objects.create_superuser(username, f"{username}@example.test", None)


def test_routes_refuse_everyone_but_the_superadmin():
    space = make_space("c13-space")
    manager = staff_account(space, "c13-sm", "space_manager")
    for name in ("admin-platform-module-defaults", "admin-platform-admins"):
        assert authenticated_client(manager).get(reverse(name)).status_code in (401, 403)


def test_module_defaults_show_core_defaults_and_space_counts():
    space = make_space("c13-defaults")
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"events"})
    space.save(update_fields=["enabled_modules"])
    body = authenticated_client(_root()).get(reverse("admin-platform-module-defaults")).json()
    assert body["spaces_total"] >= 1
    rows = {row["key"]: row for row in body["modules"]}
    assert rows["events"]["spaces_on"] >= 1
    core = [row for row in body["modules"] if row["always_on"]]
    assert core and all(row["on_for_new_spaces"] and row["spaces_on"] == body["spaces_total"] for row in core)


def test_admin_list_has_no_contact_details_and_is_audited():
    root = _root("c13-root-list")
    _root("c13-second-admin")
    response = authenticated_client(root).get(reverse("admin-platform-admins"))
    assert response.status_code == 200
    names = {row["username"] for row in response.json()["admins"]}
    assert {"c13-root-list", "c13-second-admin"} <= names
    assert "@example.test" not in response.content.decode()
    assert AuditLog.objects.filter(action="platform.admins_viewed", actor=root).exists()
