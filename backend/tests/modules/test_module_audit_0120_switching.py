"""Module audit 0.12.0: who may switch a module or feature, and the audit row every switch leaves.

Every switch writes `makerspace.capabilities_changed` (modules) or `makerspace.features_changed`
(features) with the actor, `scope` (always "space": the deployment level is environment,
read-only at runtime), `authority` (platform superadmin / space staff / system), `via` and
before -> after. Only the Space Manager and the superadmin switch; every other role is refused
and nothing changes.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.admin_capabilities import MakerspaceAdminForm, MakerspaceCapabilityAdminMixin
from apps.makerspaces.module_install import install_module
from apps.makerspaces.module_registry import core_module_keys
from apps.makerspaces.role_catalog import ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.module_helpers import disable_module
from tests.return_helpers import authenticated_client, make_space, make_user

pytestmark = pytest.mark.django_db

OTHER_ROLES = sorted(role.slug for role in ROLE_CATALOG if role.slug != "space_manager")


def _modules_url(space, action):
    return reverse(f"admin-module-{action}", args=[space.pk])


def _features_url(space):
    return f"/api/v1/admin/makerspaces/{space.pk}"


def _last(space, action):
    return AuditLog.objects.filter(makerspace=space, action=action).order_by("-id").first()


def _superadmin(name):
    return make_user(name, role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)


# --- module switches: audit -------------------------------------------------------------------


def test_a_space_manager_module_switch_is_audited_with_space_authority():
    space = make_space("audit-switch-sm")
    disable_module(space, "bookings")
    manager = staff_account(space, "audit-switch-sm-user", "space_manager")
    client = authenticated_client(manager)

    assert client.post(_modules_url(space, "install"), {"key": "bookings"}, format="json").status_code == 200
    on = _last(space, "makerspace.capabilities_changed")
    assert client.post(_modules_url(space, "uninstall"), {"key": "bookings"}, format="json").status_code == 200
    off = _last(space, "makerspace.capabilities_changed")

    assert on.actor_id == manager.pk and off.actor_id == manager.pk and on.pk != off.pk
    assert "bookings" not in on.meta["before"]["modules"] and "bookings" in on.meta["after"]["modules"]
    assert "bookings" in off.meta["before"]["modules"] and "bookings" not in off.meta["after"]["modules"]
    for row in (on, off):
        assert (row.meta["scope"], row.meta["authority"], row.meta["via"]) == ("space", "space", "modules")


def test_a_superadmin_module_switch_is_audited_with_platform_authority():
    space = make_space("audit-switch-root")
    disable_module(space, "stocktake")
    root = _superadmin("audit-switch-root-user")

    response = authenticated_client(root).post(_modules_url(space, "install"), {"key": "stocktake"}, format="json")

    row = _last(space, "makerspace.capabilities_changed")
    assert response.status_code == 200 and row.actor_id == root.pk
    assert (row.meta["scope"], row.meta["authority"]) == ("space", "platform")


def test_a_service_switch_without_a_person_is_audited_as_system():
    space = make_space("audit-switch-system")
    disable_module(space, "shop")

    install_module(space, "shop")

    row = _last(space, "makerspace.capabilities_changed")
    assert row.actor_id is None and row.meta["authority"] == "system" and "shop" in row.meta["after"]["modules"]


class _Base:
    def save_model(self, request, obj, form, change):
        obj.save()


class _ControlAdmin(MakerspaceCapabilityAdminMixin, _Base):
    def message_user(self, request, message, level):
        pass


def test_a_control_plane_matrix_save_is_audited_with_platform_authority():
    # The same harness as tests/makerspaces/test_admin_module_matrix_completion.py.
    root = get_user_model().objects.create_superuser("audit-matrix-root", "audit-matrix-root@example.test", "pw-unused-1")
    space = make_space("audit-matrix")
    space.enabled_modules = sorted(core_module_keys())
    space.save(update_fields=["enabled_modules"])
    form = MakerspaceAdminForm(instance=space)
    form.cleaned_data = {"capabilities": ["module:machine_service"]}
    form.clean_capabilities()
    request = RequestFactory().post("/control/")
    request.user = root

    _ControlAdmin().save_model(request, space, form, change=True)

    row = _last(space, "makerspace.capabilities_changed")
    assert row.actor_id == root.pk and "machine_service" in row.meta["after"]["modules"]
    assert (row.meta["scope"], row.meta["authority"], row.meta["via"]) == ("space", "platform", "control")


# --- module switches: authority -----------------------------------------------------------------


@pytest.mark.parametrize("slug", OTHER_ROLES)
def test_no_other_role_switches_a_module(slug):
    space = make_space(f"audit-deny-{slug}".replace("_", "-"))
    disable_module(space, "bookings")
    client = authenticated_client(staff_account(space, f"audit-deny-{slug}", slug))
    before = AuditLog.objects.filter(makerspace=space, action="makerspace.capabilities_changed").count()

    install = client.post(_modules_url(space, "install"), {"key": "bookings"}, format="json")
    uninstall = client.post(_modules_url(space, "uninstall"), {"key": "stocktake"}, format="json")

    assert install.status_code in {403, 404} and uninstall.status_code in {403, 404}, (install.status_code, uninstall.status_code)
    space.refresh_from_db()
    assert "bookings" not in space.enabled_modules and "stocktake" in space.enabled_modules
    assert AuditLog.objects.filter(makerspace=space, action="makerspace.capabilities_changed").count() == before


def test_the_generic_settings_patch_never_writes_modules():
    space = make_space("audit-patch-modules")
    disable_module(space, "bookings")
    client = authenticated_client(staff_account(space, "audit-patch-modules-sm", "space_manager"))

    response = client.patch(_features_url(space), {"enabled_modules": [*space.enabled_modules, "bookings"]}, format="json")

    assert response.status_code == 403
    space.refresh_from_db()
    assert "bookings" not in space.enabled_modules


# --- feature switches -------------------------------------------------------------------------


def test_a_feature_switch_is_audited_old_to_new_with_scope_and_authority():
    space = make_space("audit-feature-sm")
    manager = staff_account(space, "audit-feature-sm-user", "space_manager")
    features = [key for key in space.enabled_features if key != "safety.incidents"]
    client = authenticated_client(manager)

    response = client.patch(_features_url(space), {"enabled_features": [*features, "safety.incidents"]}, format="json")

    row = _last(space, "makerspace.features_changed")
    assert response.status_code == 200, response.data
    assert row.actor_id == manager.pk and row.meta["turned_on"] == ["safety.incidents"] and row.meta["turned_off"] == []
    assert "safety.incidents" in row.meta["after"] and "safety.incidents" not in row.meta["before"]
    assert (row.meta["scope"], row.meta["authority"], row.meta["via"]) == ("space", "space", "console")


@pytest.mark.parametrize("slug", OTHER_ROLES)
def test_no_other_role_switches_a_feature_through_the_settings_patch(slug):
    space = make_space(f"audit-fdeny-{slug}".replace("_", "-"))
    client = authenticated_client(staff_account(space, f"audit-fdeny-{slug}", slug))
    before = list(space.enabled_features)

    response = client.patch(_features_url(space), {"enabled_features": [*before, "safety.incidents"]}, format="json")

    assert response.status_code in {403, 404}, response.status_code
    space.refresh_from_db()
    assert space.enabled_features == before


def test_a_retired_switch_cannot_be_turned_on_but_a_stored_one_survives_an_edit():
    space = make_space("audit-retired")
    client = authenticated_client(staff_account(space, "audit-retired-sm", "space_manager"))
    refused = client.patch(_features_url(space), {"enabled_features": [*space.enabled_features, "machines.certifications"]},
                           format="json")
    assert refused.status_code == 400 and "machines.certifications" in str(refused.data)

    space.enabled_features = [*space.enabled_features, "machines.certifications"]
    space.save(update_fields=["enabled_features"])
    space.refresh_from_db()
    kept = client.patch(_features_url(space), {"enabled_features": [*space.enabled_features, "safety.incidents"]},
                        format="json")
    assert kept.status_code == 200, kept.data


def test_a_feature_whose_app_is_not_shipped_cannot_be_turned_on(monkeypatch):
    from tests.modules.test_module_audit_0120_registry import ship_without

    space = make_space("audit-unshipped-feature")
    space.enabled_features = [key for key in space.enabled_features if key != "machines.maintenance"]
    space.save(update_fields=["enabled_features"])
    client = authenticated_client(staff_account(space, "audit-unshipped-sm", "space_manager"))
    ship_without(monkeypatch, "maintenance")

    response = client.patch(_features_url(space), {"enabled_features": [*space.enabled_features, "machines.maintenance"]},
                            format="json")

    assert response.status_code == 400 and "machines.maintenance" in str(response.data)


def test_switches_flipped_by_the_membership_editors_are_audited():
    from apps.makerspaces.membership_admission_settings import update_settings
    from apps.makerspaces.membership_plan_policy import sync_plan_features
    from apps.makerspaces.models import MembershipPlan

    space = make_space("audit-membership-switch")
    space.enabled_features = [key for key in space.enabled_features if key != "membership.vouching"]
    space.save(update_fields=["enabled_features"])
    manager = staff_account(space, "audit-membership-sm", "space_manager")

    update_settings(manager, space, {"recipe": "free_vouch", "vouches_required": 2})
    row = _last(space, "makerspace.features_changed")
    assert row.actor_id == manager.pk and "membership.vouching" in row.meta["turned_on"]
    assert row.meta["via"] == "membership_settings"

    update_settings(manager, space, {"recipe": "free_open"})
    space.refresh_from_db()
    assert "membership.vouching" not in space.enabled_features
    MembershipPlan.objects.create(makerspace=space, name="Vouched plan", interval="monthly", join_mode="vouch")
    sync_plan_features(space, actor=manager)
    row = _last(space, "makerspace.features_changed")
    assert row.meta["via"] == "membership_plans" and row.meta["turned_on"] == ["membership.vouching"]
