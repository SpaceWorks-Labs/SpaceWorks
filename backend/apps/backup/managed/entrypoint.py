"""Maintenance secrets are admitted only for the fixed finite release/adopt argv."""

from apps.backup.process_roles import ProcessRole

from .admission import assert_binding, assert_managed_admission, deployment_id
from .release import preflight_release, release_specs


ADOPT_COMMAND = ["python", "-m", "apps.backup.managed.adopt"]


def admit_managed_command(role, command):
    if role == ProcessRole.MIGRATE or (
        role == ProcessRole.MANAGEMENT and command == ADOPT_COMMAND
    ):
        preflight_release()
    elif role == ProcessRole.MANAGEMENT and command[:3] == ["python", "manage.py", "export_tenant_migration_archive"]:
        import os
        from config.cloud_database import connect_database

        # This is the one job-only portable-export maintenance surface, not a
        # reusable owner environment group for arbitrary management commands.
        _, maintenance = release_specs()
        runtime_source = {key: value for key, value in os.environ.items() if key not in {"DATABASE_MAINTENANCE_URL", "SPACEWORKS_MAINTENANCE_DATABASE_URL", "CLOUD_SCRATCH_DATABASES_FILE"}}
        assert_managed_admission(runtime_source)
        with connect_database(maintenance) as database:
            assert_binding(database, deployment_id(), require_narrow=False)
    else:
        assert_managed_admission()
