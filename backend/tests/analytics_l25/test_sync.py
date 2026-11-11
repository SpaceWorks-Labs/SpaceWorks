"""L25: the post-migrate sync builds the objects, is idempotent, never fails a migrate, and
degrades to "not available on this hosting" where the owner cannot create roles."""

import pytest
from django.db import connection

from apps.analytics import db_ddl, db_sync, provisioning
from apps.analytics.catalogue.registry import installed_views
from apps.analytics.db_names import PLATFORM_SCHEMA, SPACE_SCHEMA, roles, tag

pytestmark = pytest.mark.django_db


def _views(schema):
    with connection.cursor() as cursor:
        cursor.execute("SELECT c.relname, pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n "
                       "ON n.oid = c.relnamespace WHERE n.nspname = %s AND c.relkind = 'v'", [schema])
        return dict(cursor.fetchall())


def _names():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        return roles(cursor.fetchone()[0])


def test_every_installed_view_exists_in_both_schemas_with_the_right_owner():
    names = _names()
    space_views, platform_views = _views(SPACE_SCHEMA), _views(PLATFORM_SCHEMA)
    for view in installed_views():
        assert space_views[view.name] == (names["powner"] if view.lookup else names["owner"])
        assert platform_views[view.name] == names["powner"]
    assert "views_catalog" in space_views and "views_catalog" in platform_views


def test_the_space_view_owner_is_in_the_fixed_group_and_the_platform_owner_is_not():
    names = _names()
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_has_role(%s, 'spaceworks_rls_fixed', 'MEMBER'), "
                       "pg_has_role(%s, 'spaceworks_rls_fixed', 'MEMBER')", [names["owner"], names["powner"]])
        assert cursor.fetchone() == (True, False)
        cursor.execute("SELECT rolcanlogin, rolbypassrls FROM pg_roles WHERE rolname = ANY(%s)",
                       [list(names.values())])
        assert set(cursor.fetchall()) == {(False, False)}


def test_the_fixed_role_policy_exists_once_the_group_does():
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_policy WHERE polname = 'spaceworks_rls_fixed'")
        assert cursor.fetchone()[0] > 0


def test_the_provisioning_functions_are_not_executable_by_public():
    with connection.cursor() as cursor:
        cursor.execute("SELECT has_function_privilege('public', %s, 'EXECUTE')", ["spaceworks_analytics_admin.ensure_login(text, text, bigint)"])
        assert cursor.fetchone()[0] is False


def test_a_second_sync_is_unchanged_and_force_rebuilds():
    assert db_sync.sync().state == "unchanged"
    result = db_sync.sync(force=True)
    assert (result.state, result.failed) == ("synced", {})
    assert db_sync.sync().state == "unchanged"


def test_an_owner_that_cannot_create_roles_is_skipped_not_failed(monkeypatch):
    monkeypatch.setattr(db_ddl, "privileges", lambda cursor: (False, False, 160000))
    result = db_sync.sync(force=True)
    assert (result.state, result.reason) == ("skipped", "cannot_create_roles")
    db_sync.post_migrate_sync(sender=None)  # never raises


def test_a_non_superuser_owner_needs_postgres_16(monkeypatch):
    monkeypatch.setattr(db_ddl, "privileges", lambda cursor: (False, True, 150000))
    assert db_sync.sync(force=True).reason == "postgres_16_required"


def test_post_migrate_swallows_errors(monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(db_sync, "sync", explode)
    db_sync.post_migrate_sync(sender=None)


def test_availability_is_false_without_the_functions(monkeypatch):
    monkeypatch.setattr(provisioning, "ENSURE_LOGIN", "spaceworks_analytics_admin.missing(text)")
    assert provisioning.availability() == (False, "not_available_on_hosting")


def test_pre_migrate_drops_the_views_only_for_a_real_plan():
    db_sync.pre_migrate_drop(sender=None, plan=[])
    assert _views(SPACE_SCHEMA)
    db_sync.pre_migrate_drop(sender=None, plan=[("migration", False)])
    assert not _views(SPACE_SCHEMA)
    db_sync.sync()
    assert _views(SPACE_SCHEMA)


def test_role_names_are_tagged_per_database():
    assert tag("db_one") != tag("db_two")
    assert roles("db_one")["reader"] != roles("db_two")["reader"]
