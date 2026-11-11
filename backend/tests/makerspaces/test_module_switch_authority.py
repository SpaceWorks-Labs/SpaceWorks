"""#128 C-10: the Space Manager switches modules (data kept); limit-gated installs stay superadmin's."""
import pytest
from django.urls import reverse

from apps.makerspaces.admin_capability_completion import complete_selection
from apps.makerspaces.module_install import uninstall_module
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


def test_space_manager_installs_and_uninstalls_on_self_host():
    space = make_space("switch-sm")
    uninstall_module(space, "bookings")
    client = authenticated_client(staff_account(space, "switch-sm-user", "space_manager"))
    groups = client.get(reverse("admin-module-groups", args=[space.pk]))
    assert groups.status_code == 200 and groups.data["deployment"] is None
    assert client.post(reverse("admin-module-install", args=[space.pk]), {"key": "bookings"},
                       format="json").status_code == 200
    assert client.post(reverse("admin-module-uninstall", args=[space.pk]), {"key": "bookings"},
                       format="json").status_code == 200


def test_limit_gated_install_is_superadmin_only_on_the_managed_platform(monkeypatch):
    space = make_space("switch-managed")
    uninstall_module(space, "bookings")
    monkeypatch.setattr("apps.makerspaces.limits.is_self_host", lambda: False)
    client = authenticated_client(staff_account(space, "switch-managed-sm", "space_manager"))
    refused = client.post(reverse("admin-module-install", args=[space.pk]), {"key": "bookings"}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "module_install_superadmin_only"
    assert client.post(reverse("admin-module-install", args=[space.pk]), {"key": "stocktake"},
                       format="json").status_code in {200, 400}


def test_other_staff_cannot_switch_modules():
    space = make_space("switch-im")
    client = authenticated_client(staff_account(space, "switch-im-user", "inventory_manager"))
    assert client.post(reverse("admin-module-uninstall", args=[space.pk]), {"key": "bookings"},
                       format="json").status_code in {403, 404}


def test_matrix_ticking_a_feature_ticks_its_required_features_and_their_parents():
    result = complete_selection([], [], ["maintenance.meters"])
    assert "machines.maintenance" in result.features and "machines" in result.modules
    assert "machines.maintenance" in result.added
    # An untick wins: the dependant goes too, nothing is re-ticked.
    result = complete_selection(["machines"], ["machines"], ["maintenance.meters"],
                                ["machines.maintenance", "maintenance.meters"])
    assert "maintenance.meters" not in result.features and "machines.maintenance" not in result.features
    assert result.turned_off_features == ["maintenance.meters"]
