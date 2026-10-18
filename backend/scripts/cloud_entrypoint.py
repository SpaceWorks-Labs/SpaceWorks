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
    if selection.mode == "managed":
        # Import the leaf by path: importing config executes Celery before admission.
        hook = runpy.run_path(str(Path(__file__).resolve().parents[1] / "config/cloud_settings/secrets.py"))
        hook["materialize"]()
    if selection.mode == "managed" and len(sys.argv) > 2 and sys.argv[2] in {"backend", "worker", "beat", "cron"}:
        from apps.backup.managed.admission import assert_managed_admission
        from config.cloud_database import database_spec, connect_database
        assert_managed_admission()
        with connect_database(database_spec(os.environ["DATABASE_URL"], managed=True)) as database:
            with database.cursor() as cursor:
                cursor.execute("SELECT generation, paused_by FROM backup_managedcapturestate WHERE id=1")
                row = cursor.fetchone()
                if row is None or row[1] is not None:
                    raise ValueError("Writer generation is unavailable.")
                os.environ["SPACEWORKS_ADMITTED_GENERATION"] = str(row[0])
    runpy.run_path(str(Path(__file__).with_name("spaceworks_entrypoint.py")), run_name="__main__")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("SpaceWorks startup refused: deployment configuration or secret files invalid.", file=sys.stderr)
        raise SystemExit(78)
