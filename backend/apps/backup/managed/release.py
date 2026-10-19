"""Finite, serialized maintenance operation; owner credentials never reach web."""

import os

from apps.backup.database_grants import GrantTarget, provision_runtime_role
from config.cloud_database import connect_database, database_spec
from config.cloud_database.probes import probe_extensions, probe_session_transport

from .admission import ManagedAdmissionError, assert_binding, assert_primary, assert_recovery_normal, deployment_id
from .runtime_grants import application_tables, apply_managed_grants
from .operation_lock import OPERATION_KEY
from .data_api import prepare_private_defaults
from config.cloud_database.principal import database_principal
from .runtime_rights import grant_required_extensions, prove_runtime_rights


RELEASE_KEY = OPERATION_KEY


def release_specs(environ=None):
    source = os.environ if environ is None else environ
    if str(source.get("MANAGED_POSTGRES", "")).lower() not in {"true", "1", "yes", "on"}:
        raise ManagedAdmissionError("Managed release requires MANAGED_POSTGRES=True.")
    deployment_id(source)
    runtime = database_spec(source.get("DATABASE_URL", ""), managed=True, environ=source)
    maintenance = database_spec(
        source.get("DATABASE_MAINTENANCE_URL", ""), managed=True, environ=source,
        mode=source.get("DATABASE_MAINTENANCE_CONNECTION_MODE", ""),
        statement_timeout_ms=3600000,
    )
    if database_principal(runtime) == database_principal(maintenance):
        raise ManagedAdmissionError("Release requires distinct maintenance and runtime credentials.")
    if runtime.parameters["dbname"] != maintenance.parameters["dbname"]:
        raise ManagedAdmissionError("Maintenance and runtime database names disagree.")
    return runtime, maintenance


def preflight_release(environ=None):
    _, maintenance = release_specs(environ)
    with connect_database(maintenance) as database, database.cursor() as cursor:
        assert_primary(cursor)


def _existing(cursor, *, adopt, expected=None):
    cursor.execute("SELECT to_regclass('public.django_migrations')")
    existing = cursor.fetchone()[0] is not None
    if existing:
        assert_recovery_normal(cursor)
        cursor.execute("SELECT run_id, capture_id FROM public.backup_deploymentdatabaseidentity WHERE id=1")
        if cursor.fetchone() != (None, None):
            raise ManagedAdmissionError("Restored database lineage requires offline recovery qualification.")
        cursor.execute("SELECT to_regclass('public.backup_manageddeploymentstate')")
        binding_table = cursor.fetchone()[0]
        if binding_table is not None:
            cursor.execute("SELECT deployment_id::text, database_uuid::text FROM public.backup_manageddeploymentstate WHERE id=1")
            binding = cursor.fetchone()
            cursor.execute("SELECT database_uuid::text FROM public.backup_deploymentdatabaseidentity WHERE id=1")
            identity = cursor.fetchone()
            if binding is not None and binding != (str(expected), identity[0]):
                raise ManagedAdmissionError("Existing managed binding disagrees with the release identity.")
            if binding is None and not adopt:
                raise ManagedAdmissionError("Existing installations require explicit managed adoption.")
        elif not adopt:
            raise ManagedAdmissionError("Existing installations require explicit managed adoption.")
        from .legacy_staging import assert_durable_staging
        assert_durable_staging(cursor)
    else:
        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r', 'p'))")
        if cursor.fetchone()[0]:
            raise ManagedAdmissionError("Initial bootstrap requires an empty application schema.")
    return existing


def run_release(*, adopt=False):
    """Use only from the exact entrypoint release/adopt argv, never a web action."""
    runtime, maintenance = release_specs()
    expected = deployment_id()
    probe_session_transport(maintenance)
    with connect_database(maintenance) as lock_database:
        with lock_database.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", list(RELEASE_KEY))
            if not cursor.fetchone()[0]:
                raise ManagedAdmissionError("Another release is already running.")
            existing = _existing(cursor, adopt=adopt, expected=expected)
            prepare_private_defaults(cursor)
            cursor.execute("SELECT pg_backend_pid()")
            pid = cursor.fetchone()[0]
        from config.cloud_database.guards import TransactionGuard

        guard = TransactionGuard(lock_database, pid, RELEASE_KEY)
        # The release is a dedicated process, so it can configure Django once with
        # its maintenance URL. Ordinary admission rejects this secret entirely.
        os.environ["DATABASE_URL"] = os.environ["DATABASE_MAINTENANCE_URL"]
        os.environ["DATABASE_CONNECTION_MODE"] = maintenance.mode
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django

        django.setup()
        from django.apps import apps
        from django.core.management import call_command
        from django.db import connection, transaction
        from apps.audit.services import record
        from .models import ManagedCaptureState, ManagedDeploymentState
        from apps.backup.models import DeploymentRecoveryState
        from apps.backup.models_host_identity import DeploymentDatabaseIdentity

        guard.assert_valid()
        def fenced_query(execute, sql, params, many, context):
            guard.assert_valid()
            return execute(sql, params, many, context)

        with connection.execute_wrapper(fenced_query):
            call_command("migrate", interactive=False)
        guard.assert_valid()
        with transaction.atomic():
            identity = DeploymentDatabaseIdentity.objects.get(pk=1)
            # Migration 0022 seeds this row; never recreate or reset it here.
            if DeploymentRecoveryState.objects.get(pk=1).mode != "normal":
                raise ManagedAdmissionError("Release cannot reset recovery state.")
            state = ManagedDeploymentState.objects.filter(pk=1).first()
            if state is None:
                if existing and not adopt:
                    raise ManagedAdmissionError("Explicit adoption is required for this database.")
                ManagedDeploymentState.objects.create(pk=1, deployment_id=expected, database_uuid=identity.database_uuid)
                ManagedCaptureState.objects.create(pk=1)
                if existing:
                    record(None, "deployment.managed_adopted", meta={"profile": os.environ.get("SPACEWORKS_DEPLOYMENT_PROFILE", "full")})
                else:
                    record(None, "deployment.managed_initialized", meta={"profile": os.environ.get("SPACEWORKS_DEPLOYMENT_PROFILE", "full")})
            elif state.deployment_id != expected or state.database_uuid != identity.database_uuid:
                raise ManagedAdmissionError("Managed binding disagrees with this deployment.")
        # Wizard answers and its generated password are release-only environment
        # values. Run the existing idempotent setup under the same release fence;
        # ordinary upgrades without confirmed setup choices never create defaults.
        if os.environ.get("SETUP_SUPERADMIN_USERNAME"):
            with connection.execute_wrapper(fenced_query):
                call_command("setup_instance")
            guard.assert_valid()
        with connection.cursor() as cursor:
            tables = {model._meta.db_table for model in apps.get_models(include_auto_created=True) if model._meta.managed}
            tables.add("django_migrations")
            application_tables(cursor, tables)
            probe_extensions(cursor)
        guard.assert_valid()
        with connect_database(maintenance) as database, database.cursor() as cursor:
            target = GrantTarget(maintenance.parameters["dbname"], database_principal(runtime))
            provision_runtime_role(cursor, target, runtime.parameters.get("password", ""))
            apply_managed_grants(cursor, target.runtime_role, tables)
            grant_required_extensions(cursor, target.runtime_role)
            from psycopg2 import sql

            cursor.execute(sql.SQL("ALTER ROLE {} LOGIN").format(sql.Identifier(target.runtime_role)))
        with connect_database(runtime) as database:
            assert_binding(database, expected)
            with database.cursor() as cursor:
                probe_extensions(cursor)
                prove_runtime_rights(cursor, tables)
        guard.assert_valid()
        # Exit/close releases the advisory lock, including all error exits.
