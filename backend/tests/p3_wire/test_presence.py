from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.models import Makerspace
from apps.makerspaces.validators import DEFAULT_PRESENCE_PRESETS
from apps.presence.models import PresencePreference, PresenceSettings
from apps.presence.services import staff_check_in

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("show_names,opt_out,hidden", [(False, True, False), (True, False, True), (True, True, True), (True, True, False)])
@pytest.mark.parametrize("checked_in", [False, True])
def test_current_session_always_exposes_effective_privacy_policy(world, show_names, opt_out, hidden, checked_in):
    PresenceSettings.objects.update_or_create(makerspace=world.space,
        defaults={"show_names": show_names, "allow_personal_opt_out": opt_out})
    PresencePreference.objects.create(makerspace=world.space, account=world.owner, hide_on_display=hidden)
    if checked_in:
        staff_check_in(world.staff, world.owner, world.space, 120, status="visiting")
    response = world.client(world.owner).get(reverse("presence-current", kwargs={"makerspace_slug": world.space.slug}))
    assert response.status_code == 200, response.data
    assert response.data["active"] is checked_in
    assert response.data["personal_opt_out_allowed"] is opt_out
    assert response.data["names_displayed"] is (show_names and not (opt_out and hidden))
    assert response.data["presets"] == [60, 120, 180, 240] == DEFAULT_PRESENCE_PRESETS


def test_empty_staff_roster_carries_policy_at_top_level(world):
    PresenceSettings.objects.update_or_create(makerspace=world.space,
        defaults={"show_names": False, "allow_personal_opt_out": False})
    response = world.client(world.staff).get(reverse("admin-presence-sessions-current", kwargs={"makerspace_id": world.space.pk}))
    assert response.status_code == 200, response.data
    assert response.data["results"] == [] and response.data["count"] == 0
    assert response.data["personal_opt_out_allowed"] is False and response.data["names_displayed"] is False


def test_presence_module_rollout_is_idempotent_and_preserves_other_choices():
    rollout = import_module("apps.makerspaces.migrations.0096_enable_existing_presence")
    existing = Makerspace.objects.create(name="Existing", slug="wire-existing", enabled_modules=["inventory", "membership"])
    installed = Makerspace.objects.create(name="Installed", slug="wire-installed", enabled_modules=["inventory", "presence"])
    hidden = Makerspace.objects.create(name="Archived", slug="wire-archived", archived_at=timezone.now(), enabled_modules=[])
    rollout.enable_existing_presence(apps, SimpleNamespace(connection=connection))
    rollout.enable_existing_presence(apps, SimpleNamespace(connection=connection))
    for row in (existing, installed, hidden):
        row.refresh_from_db()
        assert row.enabled_modules.count("presence") == 1
    assert existing.enabled_modules == ["inventory", "membership", "presence"]
    assert installed.enabled_modules == ["inventory", "presence"]


def test_presence_rollout_does_not_change_new_space_registry_default(monkeypatch):
    from apps.makerspaces.models import default_enabled_modules
    from apps.makerspaces.module_registry import default_enabled_module_keys
    monkeypatch.setattr(Makerspace._meta.get_field("enabled_modules"), "default", default_enabled_modules)
    monkeypatch.delitem(Makerspace._meta.get_field("enabled_modules").__dict__, "_get_default", raising=False)
    fresh = Makerspace.objects.create(name="Fresh default", slug="wire-default")
    assert set(fresh.enabled_modules) == set(default_enabled_module_keys())
    assert "presence" not in fresh.enabled_modules


def test_presence_migration_chains_after_actual_previous_leaf():
    migration = import_module("apps.makerspaces.migrations.0096_enable_existing_presence").Migration
    assert migration.dependencies == [("makerspaces", "0095_booking_requester_notifications_default_on")]
