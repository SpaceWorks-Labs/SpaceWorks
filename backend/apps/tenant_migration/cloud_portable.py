"""Finite-job qualification and two isolated, operator-owned scratch databases."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
import uuid

from django.apps import apps
from django.conf import settings
from django.db import connections
from psycopg2 import sql

from config.cloud_database import connect_database, database_spec
from config.cloud_database.scratch import scratch_specs, qualify_scratch, ScratchUnavailable
from config.cloud_database.guards import TransactionGuard

_allocated = ContextVar("managed_scratch_allocations", default={})
_qualified = ContextVar("qualified_scratch_specs", default=())
SCRATCH_KEY = (734323, 1)


def _specs():
    return scratch_specs(os.environ.get("CLOUD_SCRATCH_DATABASES_FILE", ""))


def as_database(spec):
    # Preserve all validated TLS options; no secondary runtime alias is created.
    parameters = spec.parameters
    base = dict(settings.DATABASES["default"])
    base.update(NAME=parameters["dbname"], USER=parameters["user"], PASSWORD=parameters.get("password", ""),
                HOST=parameters["host"], PORT=parameters.get("port", 5432), CONN_MAX_AGE=0,
                OPTIONS={key: value for key, value in parameters.items()
                         if key not in {"dbname", "user", "password", "host", "port"}})
    return base


def qualify_portable_export():
    if settings.SPACEWORKS_DEPLOYMENT_PROFILE == "free":
        raise ScratchUnavailable("Portable database capture requires a finite full-profile maintenance job.")
    if os.environ.get("SPACEWORKS_FINITE_MAINTENANCE_JOB") != "1":
        raise ScratchUnavailable("Run portable capture through the admitted finite maintenance command.")
    from apps.backup.managed.release import release_specs
    from apps.backup.managed.admission import assert_binding, deployment_id
    from apps.backup.managed.runtime_grants import application_tables
    runtime, maintenance = release_specs()
    with connect_database(maintenance) as database, database.cursor() as cursor:
        facts = assert_binding(database, deployment_id(), require_narrow=False)
        cursor.execute("SELECT database_uuid FROM backup_deploymentdatabaseidentity WHERE id=1")
        application_uuid = cursor.fetchone()[0]
        application_tables(cursor, registered_tables())
    specs = _specs()
    if len({spec.parameters["dbname"] for spec in specs}) != 2:
        raise ScratchUnavailable("Provision two distinctly named scratch databases before portable capture.")
    qualify_scratch(specs, application_uuid=application_uuid, runtime_roles=[runtime.parameters["user"]])
    qualified = []
    for spec in specs:
        with connect_database(spec) as scratch, scratch.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            if int(cursor.fetchone()[0]) // 10000 != facts["database_major"]:
                raise ScratchUnavailable("Scratch and source PostgreSQL majors must agree.")
            cursor.execute("SELECT database_uuid FROM public.spaceworks_scratch_identity WHERE id=1")
            qualified.append((spec, str(cursor.fetchone()[0]), runtime.parameters["user"]))
    _qualified.set(tuple(qualified))
    if not settings.TENANT_MIGRATION_AGE_RECIPIENT or not settings.TENANT_MIGRATION_AGE_IDENTITY_FILE:
        raise ScratchUnavailable("Configure the private staging age identity before source freeze.")
    from apps.backup.cloud_operations import require_managed_tenant_capture
    require_managed_tenant_capture()
    return facts


def registered_tables():
    return {model._meta.db_table for model in apps.get_models(include_auto_created=True)
            if model._meta.managed and not model._meta.proxy} | {"django_migrations", "spaceworks_cache"}


def allocated_database(name):
    value = _allocated.get().get(name)
    return value[0] if value else None


def ensure_qualified():
    if not _qualified.get():
        qualify_portable_export()


def check_allocations():
    for _database, guard in _allocated.get().values():
        guard.assert_valid()


def application_table_names(using):
    names = connections[using].introspection.table_names()
    if settings.SPACEWORKS_DEPLOYMENT_MODE == "managed":
        check_allocations()
        if allocated_database(connections[using].settings_dict["NAME"]) is None:
            raise ScratchUnavailable("The inspected database has no retained scratch allocation.")
        names = [name for name in names if name != "spaceworks_scratch_identity"]
    return names


@contextmanager
def allocate(alias, *, migrate=False):
    """Never DROP a database: only reset an exclusively held, proven scratch schema."""
    from .tenant_dump_database import _register_alias, _remove_alias, _migrate_scratch
    for spec, expected_uuid, runtime_role in _qualified.get():
        with connect_database(spec) as database:
            with database.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid(), pg_try_advisory_lock(%s,%s)", SCRATCH_KEY)
                pid, acquired = cursor.fetchone()
                if not acquired:
                    continue
                guard = TransactionGuard(database, pid, SCRATCH_KEY)
                cursor.execute("SELECT database_uuid, non_routable FROM public.spaceworks_scratch_identity WHERE id=1")
                identity, non_routable = cursor.fetchone()
                cursor.execute("SELECT has_database_privilege(%s,current_database(),'CONNECT')", [runtime_role])
                runtime_connect = cursor.fetchone()[0]
                if not non_routable or str(identity) != expected_uuid or runtime_connect:
                    raise ScratchUnavailable("Scratch identity is routable.")
            name = spec.parameters["dbname"]
            if name in _allocated.get():
                continue
            configuration = as_database(spec)
            token = _allocated.set({**_allocated.get(), name: (configuration, guard)})
            try:
                _reset(database, identity, guard)
                _register_alias(alias, name, configuration)
                try:
                    if migrate:
                        _migrate_scratch(name, configuration)
                    yield alias, name
                    guard.assert_valid()
                finally:
                    _remove_alias(alias)
                # Cleanup is explicit and guarded. Crash leaves a nonempty scratch
                # requiring fresh qualification; age does not authorize destruction.
                _reset(database, identity, guard)
            finally:
                _allocated.reset(token)
            return
    raise ScratchUnavailable("No exclusively available scratch database exists.")


def _reset(database, identity, guard):
    guard.assert_valid()
    with database.cursor() as cursor:
        cursor.execute("SELECT NOT pg_is_in_recovery(), datdba=(SELECT oid FROM pg_roles WHERE rolname=current_user) FROM pg_database WHERE datname=current_database()")
        if cursor.fetchone() != (True, True):
            raise ScratchUnavailable("Scratch database ownership changed.")
        cursor.execute("BEGIN")
        try:
            cursor.execute("DROP SCHEMA public CASCADE")
            cursor.execute("CREATE SCHEMA public")
            cursor.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            cursor.execute("CREATE TABLE public.spaceworks_scratch_identity (id integer PRIMARY KEY CHECK(id=1), database_uuid uuid NOT NULL, non_routable boolean NOT NULL)")
            cursor.execute("INSERT INTO public.spaceworks_scratch_identity VALUES (1,%s,true)", [str(identity)])
            cursor.execute("COMMIT")
        except BaseException:
            cursor.execute("ROLLBACK")
            raise


def prepare_source_restore(using):
    """Data-only source capture uses the exact installed migration schema."""
    check_allocations()
    connection = connections[using]
    with connection.cursor() as cursor:
        tables = sorted(registered_tables())
        for table in tables:
            cursor.execute(sql.SQL("ALTER TABLE public.{} DISABLE TRIGGER USER").format(sql.Identifier(table)))
        cursor.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
            sql.SQL(",").join(sql.Identifier("public", table) for table in tables)))


def finish_source_restore(using):
    with connections[using].cursor() as cursor:
        for table in sorted(registered_tables()):
            cursor.execute(sql.SQL("ALTER TABLE public.{} ENABLE TRIGGER USER").format(sql.Identifier(table)))
    check_allocations()
