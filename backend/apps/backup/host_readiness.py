"""Database-aware readiness checks bound to the immutable host marker."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from .host_marker import MarkerError, read_marker
from .process_roles import ProcessRole, admission_for


class HostReadinessError(RuntimeError):
    pass


def _identity(cursor):
    cursor.execute("SELECT current_database(), oid FROM pg_database WHERE datname = current_database()")
    return cursor.fetchone()


def assert_host_ready(marker_path):
    from .managed.profile import deployment_profile

    if deployment_profile().mode == "managed":
        from .managed.admission import assert_managed_ready

        try:
            return assert_managed_ready()
        except Exception:
            raise HostReadinessError("Managed deployment readiness could not be verified.") from None
    try:
        marker = read_marker(marker_path)
    except MarkerError as exc:
        raise HostReadinessError(str(exc)) from exc
    if not admission_for(marker.state, ProcessRole.BACKEND).admitted:
        raise HostReadinessError("Marker state does not admit a backend readiness process.")
    try:
        bound_database = marker.require_bound_database()
    except MarkerError as exc:
        raise HostReadinessError(str(exc)) from exc
    try:
        with connection.cursor() as cursor:
            from .managed.mode_binding import assert_mode_binding

            assert_mode_binding(cursor, "host")
            database_name, database_oid = _identity(cursor)
            if (database_name, database_oid) != (
                bound_database.name,
                bound_database.oid,
            ):
                raise HostReadinessError("Live database identity disagrees with the host marker.")
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise HostReadinessError("Database migrations are not at the application leaves.")
    except HostReadinessError:
        raise
    except Exception as exc:
        raise HostReadinessError("Host/database readiness facts could not be verified.") from exc
    return {
        "marker_state": marker.state.value,
        "database_routing": marker.database_routing,
        "database_oid": database_oid,
        "migrations": "applied",
    }
