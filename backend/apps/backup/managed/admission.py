"""Uncached managed launch/readiness checks; no H1 marker or socket emulation."""

import os
import uuid

from apps.backup.database_grants import _assert_narrow_runtime_role
from apps.backup.database_identity import query_live_database_identity
from config.cloud_database import connect_database, database_spec


class ManagedAdmissionError(RuntimeError):
    code = "managed_admission_refused"


def deployment_id(environ=None):
    source = os.environ if environ is None else environ
    try:
        return uuid.UUID(source.get("SPACEWORKS_DEPLOYMENT_ID", ""))
    except (ValueError, TypeError, AttributeError):
        raise ManagedAdmissionError("A stable SPACEWORKS_DEPLOYMENT_ID UUID is required.") from None


def assert_primary(cursor):
    cursor.execute("SELECT NOT pg_is_in_recovery(), current_setting('transaction_read_only') = 'off', current_setting('server_version_num')::int / 10000")
    primary, writable, major = cursor.fetchone()
    if not primary or not writable or major not in {16, 17}:
        raise ManagedAdmissionError("Managed admission requires a writable PostgreSQL 16 or 17 primary.")
    return major


def assert_recovery_normal(cursor):
    cursor.execute("SELECT mode, active_restore_id FROM public.backup_deploymentrecoverystate WHERE id = 1")
    if cursor.fetchone() != ("normal", None):
        raise ManagedAdmissionError("Recovery state is missing or does not admit managed services.")
    cursor.execute("SELECT EXISTS (SELECT 1 FROM public.backup_b1restorecomponentstate WHERE state <> 'restored') OR EXISTS (SELECT 1 FROM public.backup_b1reservationentry)")
    if cursor.fetchone()[0]:
        raise ManagedAdmissionError("Outstanding restore components or reservations require host recovery.")


def assert_binding(database, expected, *, require_narrow=True):
    live = query_live_database_identity(database)
    with database.cursor() as cursor:
        major = assert_primary(cursor)
        assert_recovery_normal(cursor)
        cursor.execute("SELECT deployment_id::text, database_uuid::text FROM public.backup_manageddeploymentstate WHERE id = 1")
        if cursor.fetchone() != (str(expected), live.database_uuid):
            raise ManagedAdmissionError("Managed deployment identity is missing or disagrees with this database.")
        from .legacy_staging import assert_durable_staging
        assert_durable_staging(cursor)
        if require_narrow:
            cursor.execute("SELECT current_user")
            _assert_narrow_runtime_role(cursor, cursor.fetchone()[0])
            cursor.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname=current_user")
            if cursor.fetchone() != (True,):
                raise ManagedAdmissionError("Runtime principal must have LOGIN privilege.")
            cursor.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE'), has_database_privilege(current_user, current_database(), 'CREATE')")
            if any(cursor.fetchone()):
                raise ManagedAdmissionError("Runtime principal must not have schema/database CREATE privileges.")
    return {"mode": "managed", "database_major": major, "recovery": "normal"}


def assert_managed_admission(environ=None):
    source = os.environ if environ is None else environ
    if source.get("DATABASE_MAINTENANCE_URL") or source.get("SPACEWORKS_MAINTENANCE_DATABASE_URL") or source.get("CLOUD_SCRATCH_DATABASES_FILE"):
        raise ManagedAdmissionError("Ordinary services must not receive maintenance or scratch credentials.")
    if str(source.get("MANAGED_POSTGRES", "")).lower() not in {"true", "1", "yes", "on"}:
        raise ManagedAdmissionError("Managed deployments require MANAGED_POSTGRES=True.")
    expected = deployment_id(source)
    try:
        spec = database_spec(source.get("DATABASE_URL", ""), managed=True, environ=source)
        with connect_database(spec) as database:
            return {**assert_binding(database, expected), "database_transport": spec.mode}
    except ManagedAdmissionError:
        raise
    except Exception:
        raise ManagedAdmissionError("Managed database admission could not be verified.") from None


def assert_managed_ready():
    """I calls this from readiness, preserving mandatory encryption checks there."""
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    facts = assert_managed_admission()
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise ManagedAdmissionError("Database migrations are not at the application leaves.")
    return {**facts, "migrations": "applied"}


def refuse_host_operation(code):
    """I places this before producer checks, artifact/workspace writes and effects."""
    from .profile import deployment_profile

    managed = deployment_profile().mode == "managed"
    if not managed:
        from django.db import connection
        from .mode_binding import assert_mode_binding

        try:
            with connection.cursor() as cursor:
                assert_mode_binding(cursor, "host")
        except Exception:
            managed = True  # Unknown identity never permits a destructive operation.
    if managed:
        error = ManagedAdmissionError("This operation requires the supervised host deployment.")
        error.code = code
        raise error
