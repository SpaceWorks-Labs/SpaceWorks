#!/usr/bin/env python3
"""Materialize managed secrets before the unchanged role/admission entrypoint."""
import os
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from cloud_contracts.deployment import parse_selection
    selection = parse_selection(os.environ)
    os.environ.pop("SPACEWORKS_FINITE_MAINTENANCE_JOB", None)
    finite_maintenance = (sys.argv[1:3] == ["--role", "management"]
        and sys.argv[3:5] == ["python", "manage.py"] and len(sys.argv) > 5
        and sys.argv[5] in {"export_tenant_migration_archive", "export_portable_tenant_dump"})
    if selection.mode == "managed" and finite_maintenance:
        os.environ["SPACEWORKS_FINITE_MAINTENANCE_JOB"] = "1"
    if selection.mode == "managed":
        # Import the leaf by path: importing config executes Celery before admission.
        hook = runpy.run_path(str(Path(__file__).resolve().parents[1] / "config/cloud_settings/secrets.py"))
        hook["materialize"]()
    ordinary = len(sys.argv) > 2 and sys.argv[2] in {"backend", "worker", "beat", "cron"}
    finite = len(sys.argv) > 5 and sys.argv[2] == "management" and sys.argv[3:5] == ["python", "manage.py"]
    if selection.mode == "managed" and (ordinary or finite):
        from apps.backup.managed.admission import assert_managed_admission
        from config.cloud_database import database_spec, connect_database
        source = dict(os.environ)
        if finite_maintenance:
            for name in ("DATABASE_MAINTENANCE_URL", "SPACEWORKS_MAINTENANCE_DATABASE_URL", "CLOUD_SCRATCH_DATABASES_FILE"):
                source.pop(name, None)
        assert_managed_admission(source)
        with connect_database(database_spec(os.environ["DATABASE_URL"], managed=True)) as database:
            with database.cursor() as cursor:
                cursor.execute("SELECT generation, paused_by FROM backup_managedcapturestate WHERE id=1")
                row = cursor.fetchone()
                recovery = finite and sys.argv[5] in {"recover_managed_capture", "resume_cloud_storage"}
                if row is None or (row[1] is not None and not recovery):
                    raise ValueError("Writer generation is unavailable.")
                os.environ["SPACEWORKS_ADMITTED_GENERATION"] = str(row[0])
    if selection.mode == "managed":
        # Processes exec'd from here import the image's cloud_setup tooling.
        scripts = str(Path(__file__).resolve().parent)
        os.environ["PYTHONPATH"] = os.pathsep.join([scripts, str(Path(scripts).parent)])
    entrypoint = runpy.run_path(str(Path(__file__).with_name("spaceworks_entrypoint.py")), run_name="spaceworks_entrypoint")
    raise SystemExit(entrypoint["main"]())


def run():
    try:
        main()
    except Exception:
        print("SpaceWorks startup refused: deployment configuration or secret files invalid.", file=sys.stderr)
        raise SystemExit(78)


if __name__ == "__main__":
    run()
