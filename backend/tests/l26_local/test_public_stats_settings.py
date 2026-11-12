"""L26 (#170): Settings › Public stats through the settings authority (SM only, superadmin parity)."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.makerspaces.settings_authority_writes import set_grants
from tests.account_split.p1_helpers import staff
from tests.events.collab_helpers import client_for

pytestmark = pytest.mark.django_db
BODY = {"enabled": True, "sections": ["community", "events", "lending"], "period": "fy",
        "headline": ["community.active_members", "events.held"], "tv_mode_enabled": True, "tv_refresh_seconds": 45}


def world(slug="l26-settings"):
    from apps.makerspaces.module_registry import core_module_keys
    space = Makerspace.objects.create(name=slug, slug=slug, enabled_modules=[*core_module_keys(), "events", "machines"])
    return space, staff(space, username=f"{slug}-sm", role="space_manager")[0]


def path(space):
    return f"/api/v1/admin/makerspace/{space.pk}/public-stats-settings"


def test_space_manager_saves_every_key_audited_as_settings_changed():
    space, sm = world()
    read = client_for(sm).get(path(space))
    assert read.status_code == 200 and read.data["can_edit"] is True
    assert read.data["capabilities"]["settings"]["sections"]["can_lock"] is False
    assert read.data["capabilities"]["visibility"]["lending.loans"]["can_lock"] is True
    assert {key: value for key, value in read.data["settings"].items() if key != "visibility"} == {"enabled": False, "sections": ["machines", "printing", "lending"],
                                     "period": "month", "headline": [], "tv_mode_enabled": False,
                                     "tv_refresh_seconds": 60}
    assert {row["key"] for row in read.data["choices"]["sections"]} == {
        "events", "machines", "printing", "lending", "community"}
    saved = client_for(sm).put(path(space), BODY, format="json")
    assert saved.status_code == 200, saved.data
    assert {key: value for key, value in saved.data["settings"].items() if key != "visibility"} == BODY
    assert all(saved.data["settings"]["visibility"].values())
    space.refresh_from_db()
    assert space.public_stats_sections == "community,events,lending" and space.public_stats_period == "fy"
    rows = AuditLog.objects.filter(action="settings.changed", meta__module="public_site")
    assert {row.meta["key"] for row in rows} == {f"public_stats.{name}" for name in BODY}
    assert all(row.meta["via"] == "space_manager" for row in rows)
    assert rows.get(meta__key="public_stats.sections").meta["to"] == ["community", "events", "lending"]
    again = client_for(sm).put(path(space), BODY, format="json")
    assert again.status_code == 200 and rows.count() == len(BODY)  # no change, no new rows


@pytest.mark.parametrize("role", ["inventory_manager", "machine_manager"])
def test_other_staff_read_only_even_with_a_module_grant(role):
    space, sm = world(f"l26-ro-{role[:3]}")
    other = staff(space, username=f"l26-{role}", role=role)[0]
    set_grants(sm, space, "inventory" if role == "inventory_manager" else "machines", [other.pk])
    read = client_for(other).get(path(space))
    assert read.status_code == 200 and read.data["can_edit"] is False
    refused = client_for(other).put(path(space), BODY, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "setting_not_delegated"
    space.refresh_from_db()
    assert space.public_stats_enabled is False
    assert not AuditLog.objects.filter(action="settings.changed", meta__module="public_site").exists()


def test_member_and_anonymous_are_refused():
    space, _sm = world("l26-member")
    member = User.objects.create_user("l26-member-person", email="m@example.test", access_status="active")
    assert client_for(member).put(path(space), BODY, format="json").status_code in {403, 404}
    assert APIClient().get(path(space)).status_code in {401, 403}


def test_superadmin_parity_in_any_space():
    space, _sm = world("l26-root")
    root = User.objects.create_superuser(username="l26-root", email="root@example.test", role=User.Role.SUPERADMIN,
                                        is_superuser=True, is_staff=True, access_status=User.AccessStatus.ACTIVE)
    read = client_for(root).get(path(space))
    assert read.status_code == 200 and read.data["can_edit"] is True
    assert client_for(root).put(path(space), BODY, format="json").status_code == 200
    assert AuditLog.objects.filter(action="settings.changed", actor=root, meta__key="public_stats.period").exists()


@pytest.mark.parametrize("change", [
    {"sections": ["events", "events"]}, {"sections": ["weather"]}, {"period": "week"},
    {"headline": ["events.held", "events.upcoming", "events.attendees", "lending.loans", "lending.library"]},
    {"headline": ["community.names"]}, {"tv_refresh_seconds": 29},
])
def test_invalid_values_are_refused(change):
    space, sm = world(f"l26-bad-{abs(hash(str(change))) % 10000}")
    response = client_for(sm).put(path(space), {**BODY, **change}, format="json")
    assert response.status_code == 400


def test_saving_invalidates_the_public_page_cache():
    space, sm = world("l26-invalidate")
    client_for(sm).put(path(space), {**BODY, "sections": ["lending"]}, format="json")
    public = APIClient().get(f"/api/v1/public/{space.slug}/stats/")
    assert public.status_code == 200 and public.data["sections"] == ["lending"]
    assert public.data["tv"] == {"enabled": True, "refresh_seconds": 45}
    client_for(sm).put(path(space), {**BODY, "sections": ["lending"], "tv_refresh_seconds": 90}, format="json")
    assert APIClient().get(f"/api/v1/public/{space.slug}/stats/").data["tv"]["refresh_seconds"] == 90


def test_openapi_documents_both_routes():
    schema = APIClient().get(reverse("schema")).content.decode()
    assert "/api/v1/admin/makerspace/{makerspace_id}/public-stats-settings" in schema
    assert "PublicStatsPage" in schema


@pytest.mark.parametrize("role,module,key", [
    ("inventory_manager", "inventory", "lending.current_loans"),
    ("event_manager", "events", "events.upcoming_list"),
    ("booking_manager", "bookings", "community.bookings"),
    ("machine_manager", "machines", "machines.hours"),
])
def test_own_area_visibility_uses_existing_grant_and_audits_each_key(role, module, key):
    from tests.fixed_roles.helpers import staff_account
    from apps.makerspaces.models_settings_authority import ModuleSettingsGrant

    space, sm = world(f"stats-delegated-{module}")
    actor = staff_account(space, f"stats-{module}-manager", role)
    client = client_for(actor)
    assert client.patch(path(space), {"visibility": {key: False}}, format="json").status_code == 403
    set_grants(sm, space, module, [actor.pk])
    grant = ModuleSettingsGrant.objects.get(makerspace=space, module=module, grantee=actor, revoked_at=None)
    response = client.patch(path(space), {"visibility": {key: False}}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["can_edit"] is False  # legacy flag remains page-wide authority
    assert response.data["settings"]["visibility"][key] is False
    assert response.data["capabilities"]["visibility"][key]["editable"] is True
    assert response.data["capabilities"]["visibility"][key]["can_lock"] is False
    assert response.data["capabilities"]["settings"]["enabled"]["editable"] is False
    row = AuditLog.objects.get(action="settings.changed", actor=actor)
    assert row.meta["module"] == module and row.meta["key"] == f"public_stats.visibility.{key}"
    assert row.meta["via"] == "module_grant" and row.meta["grant_id"] == grant.pk
    assert row.meta["from"] is True and row.meta["to"] is False
    set_grants(sm, space, module, [])
    # A no-op does not bypass a revoked grant.
    assert client.patch(path(space), {"visibility": {key: False}}, format="json").status_code == 403


def test_cross_area_or_pagewide_keys_refuse_the_whole_partial_request():
    from tests.fixed_roles.helpers import staff_account

    space, sm = world("stats-atomic")
    actor = staff_account(space, "stats-atomic-inventory", "inventory_manager")
    set_grants(sm, space, "inventory", [actor.pk])
    client = client_for(actor)
    for values in ({"visibility": {"lending.current_loans": False, "events.held": False}},
                   {"visibility": {"lending.current_loans": False}, "enabled": False}):
        response = client.patch(path(space), values, format="json")
        assert response.status_code == 403 and response.data["code"] == "setting_not_delegated"
        space.refresh_from_db()
        assert space.public_stats_config == {} and space.public_stats_enabled is False
        assert not AuditLog.objects.filter(action="settings.changed", actor=actor).exists()


def test_combined_roles_need_each_areas_grant_and_one_lock_refuses_all_changes():
    from tests.fixed_roles.helpers import staff_account
    from apps.makerspaces.settings_authority_writes import set_lock

    space, sm = world("stats-combined")
    actor = staff_account(space, "stats-combined-person", "inventory_manager", "event_manager")
    values = {"visibility": {"lending.current_loans": False, "events.held": False}}
    set_grants(sm, space, "inventory", [actor.pk])
    assert client_for(actor).patch(path(space), values, format="json").status_code == 403
    set_grants(sm, space, "events", [actor.pk])
    set_lock(sm, space, "public_stats.visibility.events.held", True)
    refused = client_for(actor).patch(path(space), values, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "setting_locked"
    space.refresh_from_db()
    assert space.public_stats_config == {}
    set_lock(sm, space, "public_stats.visibility.events.held", False)
    assert client_for(actor).patch(path(space), values, format="json").status_code == 200
    assert set(AuditLog.objects.filter(action="settings.changed", actor=actor).values_list("meta__module", flat=True)) == {"inventory", "events"}
    set_lock(sm, space, "public_stats.visibility.events.held", True)
    # Space Manager and superadmin parity still override module locks.
    response = client_for(sm).patch(path(space), {"visibility": {"events.held": True}}, format="json")
    assert response.status_code == 200
    permission = response.data["capabilities"]["visibility"]["events.held"]
    assert permission["editable"] is True and permission["locked"] is True and permission["can_lock"] is True


def test_type_scoped_machine_manager_cannot_change_tenant_aggregate_visibility():
    from apps.machines.models import Machine, MachineType
    from tests.fixed_roles.helpers import staff_account

    space, sm = world("stats-machine-scope")
    first = MachineType.objects.create(makerspace=space, name="First", slug="stats-first")
    other = MachineType.objects.create(makerspace=space, name="Other", slug="stats-other")
    for kind in (first, other):
        Machine.objects.create(makerspace=space, machine_type=kind, name=f"Stats {kind.name}")
    actor = staff_account(space, "stats-type-manager", "machine_manager", machine_types=[first])
    set_grants(sm, space, "machines", [actor.pk])
    read = client_for(actor).get(path(space))
    assert read.status_code == 200
    assert read.data["capabilities"]["visibility"]["machines.hours"]["editable"] is False
    assert client_for(actor).patch(path(space), {"visibility": {"machines.hours": False}}, format="json").status_code == 403
    space.refresh_from_db()
    assert space.public_stats_config == {}


@pytest.mark.parametrize("values", [{"visibility": {"unknown.statistic": False}}, {"unknown_field": False},
                                     {"visibility": {}}, {}])
def test_partial_unknown_or_empty_inputs_are_typed_validation_errors(values):
    space, sm = world("stats-invalid-" + str(len(str(values))))
    response = client_for(sm).patch(path(space), values, format="json")
    assert response.status_code == 400 and response.data["code"] == "invalid_public_stats_settings"
    assert "errors" in response.data
    space.refresh_from_db()
    assert space.public_stats_config == {}


def test_visibility_api_remains_space_scoped_and_documents_partial_update():
    space, sm = world("stats-source")
    other, _ = world("stats-other")
    assert client_for(sm).patch(path(other), {"visibility": {"lending.loans": False}}, format="json").status_code == 404
    schema = APIClient().get(reverse("schema")).data
    endpoint = schema["paths"]["/api/v1/admin/makerspace/{makerspace_id}/public-stats-settings"]
    assert {"get", "put", "patch"} <= set(endpoint)


def test_visibility_updates_merge_and_old_put_preserves_other_area_overrides():
    from tests.fixed_roles.helpers import staff_account

    space, sm = world("stats-merge")
    first = staff_account(space, "stats-merge-im", "inventory_manager")
    second = staff_account(space, "stats-merge-em", "event_manager")
    set_grants(sm, space, "inventory", [first.pk])
    set_grants(sm, space, "events", [second.pk])
    assert client_for(first).patch(path(space), {"visibility": {"lending.current_loans": False}}, format="json").status_code == 200
    assert client_for(second).patch(path(space), {"visibility": {"events.held": False}}, format="json").status_code == 200
    response = client_for(sm).put(path(space), BODY, format="json")
    assert response.status_code == 200
    assert response.data["settings"]["visibility"]["lending.current_loans"] is False
    assert response.data["settings"]["visibility"]["events.held"] is False


def test_visibility_mutation_replaces_cached_public_projection():
    from apps.inventory.models import InventoryProduct

    space, sm = world("stats-cache-visibility")
    for index in range(3):
        InventoryProduct.objects.create(makerspace=space, name=f"Public {index}", is_public=True)
    assert client_for(sm).put(path(space), {**BODY, "sections": ["lending"], "headline": ["lending.library"]}, format="json").status_code == 200
    endpoint = f"/api/v1/public/{space.slug}/stats/"
    assert APIClient().get(endpoint).data["hardware"]["library"]["library_size"] == 3
    response = client_for(sm).patch(path(space), {"visibility": {"lending.library": False}}, format="json")
    assert response.status_code == 200
    public = APIClient().get(endpoint)
    assert public.status_code == 200 and public.data["hardware"]["library"]["library_size"] is None
    assert public.data["headline"] == []


def test_settings_patch_remains_an_intentional_person_only_api_surface():
    from apps.apiclients.scope_registry_coverage import OUT_OF_SCOPE

    assert any(prefix == "api/v1/admin/" and "person" in reason for prefix, reason in OUT_OF_SCOPE)
