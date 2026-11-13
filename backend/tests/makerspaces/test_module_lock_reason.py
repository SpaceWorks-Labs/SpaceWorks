"""MODULE-UI: every module row says why it cannot be switched, as a stable code (core / not_shipped / limit)."""
import pytest
from django.urls import reverse

from apps.admin_api.views_modules import module_lock_reason
from apps.makerspaces.module_install import uninstall_module
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db

ROW = {"core": False, "available": True, "installed": True, "install_requires_superadmin": False}


def test_lock_reason_precedence():
    assert module_lock_reason({**ROW, "core": True}) == "core"
    assert module_lock_reason({**ROW, "available": False}) == "not_shipped"
    assert module_lock_reason({**ROW, "installed": False, "install_requires_superadmin": True}) == "limit"
    assert module_lock_reason(ROW) is None
    # A limit only blocks switching ON; an installed module can always be switched off.
    assert module_lock_reason({**ROW, "install_requires_superadmin": True}) is None


def test_module_list_carries_lock_reason_for_a_space_manager(monkeypatch):
    space = make_space("lock-reason")
    uninstall_module(space, "bookings")
    monkeypatch.setattr("apps.makerspaces.limits.is_self_host", lambda: False)
    space.resource_limit_overrides = {"bookings": 5}  # decision 328a: only a SET limit gates installs
    space.save(update_fields=["resource_limit_overrides"])
    client = authenticated_client(staff_account(space, "lock-reason-sm", "space_manager"))
    response = client.get(reverse("admin-module-groups", args=[space.pk]))
    assert response.status_code == 200
    rows = {row["key"]: row for group in response.data["groups"] for row in group["modules"]}
    assert all("lock_reason" in row for row in rows.values())
    assert rows["public_inventory"]["lock_reason"] == "core"
    assert rows["bookings"]["lock_reason"] == "limit"
