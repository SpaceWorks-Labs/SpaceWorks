"""Upgrade cleanup stays loadable after the updater app has been removed."""

from importlib import import_module

import pytest
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.urls import NoReverseMatch, reverse

from apps.makerspaces.module_registry import MODULE_KEYS
from tests.return_helpers import make_space

cleanup = import_module("apps.makerspaces.migrations.0087_remove_in_app_updates")


def test_removed_module_and_routes_are_absent():
    assert "updates" not in MODULE_KEYS
    assert "apps.updates" not in settings.INSTALLED_APPS
    assert not apps.is_installed("apps.updates")
    for name in ("admin-platform-update-settings", "admin-platform-update-now",
                 "admin-platform-update-recover", "admin-platform-update-rollback"):
        with pytest.raises(NoReverseMatch):
            reverse(name)


@pytest.mark.django_db
def test_migration_graph_loads_without_the_removed_app():
    loader = MigrationLoader(connection)
    assert not any(label == "updates" for label, _ in loader.graph.nodes)
    plan = loader.graph.forwards_plan(("makerspaces", "0087_remove_in_app_updates"))
    assert ("makerspaces", "0086_public_site_and_loans") in plan
    assert not any(label == "updates" for label, _ in plan)


@pytest.mark.django_db(transaction=True)
def test_upgrade_drops_old_tables_records_and_stored_key_idempotently():
    space = make_space("retired-updater")
    # Bypass the current module validator to reproduce an existing installation.
    type(space).objects.filter(pk=space.pk).update(
        enabled_modules=[*space.enabled_modules, "updates"],
    )
    recorder = MigrationRecorder(connection)
    for number in ("0001_initial", "0002_update_recovery",
                   "0003_remove_platformupdatesettings_channel"):
        recorder.record_applied("updates", number)
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE updates_platformupdatesettings (id bigint PRIMARY KEY)")
        cursor.execute("CREATE TABLE retired_update_fk (id bigint REFERENCES updates_platformupdatesettings(id))")
    try:
        with connection.schema_editor() as editor:
            cleanup.remove_update_state(apps, editor)
        assert "updates_platformupdatesettings" not in connection.introspection.table_names()
        assert not recorder.migration_qs.filter(app="updates").exists()
        space.refresh_from_db()
        assert "updates" not in space.enabled_modules
        # CASCADE removes obsolete dependent constraints without deleting other tables.
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, "retired_update_fk")
        assert not any(value.get("foreign_key") for value in constraints.values())
        with connection.schema_editor() as editor:
            cleanup.remove_update_state(apps, editor)
        loader = MigrationLoader(connection)
        loader.check_consistent_history(connection)
    finally:
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS retired_update_fk CASCADE")
            cursor.execute("DROP TABLE IF EXISTS updates_platformupdatesettings CASCADE")
        recorder.migration_qs.filter(app="updates").delete()
