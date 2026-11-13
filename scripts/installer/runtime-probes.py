#!/usr/bin/env python3
"""Bounded full-host diagnostics. Print fixed status codes, never provider errors."""
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ALLOWED = {
    "database": {"runtime_nonowner_no_pending_migrations"},
    "runtime": {"binaries_and_printable_bundle_verified"},
    "worker": {"task_roundtrip_verified", "inline_tasks_no_worker"},
    "scheduler": {"heartbeat_and_success_fresh"},
    "live": {"publish_subscribe_verified", "poll_fallback_readiness_verified"},
    "scanner": {"explicitly_disabled", "fresh_signatures_clean_and_infected_verified"},
    "storage": {"private_public_presign_bytes_verified"},
    "edge": {"explicit_loopback_http", "trusted_certificate_and_edge_readiness_verified"},
    "email": {"not_selected_configure_and_test_in_control", "provider_accepted_check_recipient_inbox"},
}


def database():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from probe_common import ProbeError
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise ProbeError("pending_migrations")
    with connection.cursor() as cursor:
        cursor.execute("SELECT r.rolsuper, current_user = pg_get_userbyid(d.datdba) "
                       "FROM pg_roles r, pg_database d WHERE r.rolname=current_user "
                       "AND d.datname=current_database()")
        row = cursor.fetchone()
        if row is None or any(row):
            raise ProbeError("runtime_database_privileges")
    return "runtime_nonowner_no_pending_migrations"


def runtime():
    from probe_common import ProbeError
    for binary in ("age", "age-keygen", "ffprobe"):
        if not shutil.which(binary):
            raise ProbeError("missing_runtime_binary")
    subprocess.run([sys.executable, "-m", "scripts.verify_printable_runtime", "--bundle"],
                   check=True, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "binaries_and_printable_bundle_verified"


def scheduler():
    from probe_services import scheduler as verify
    from probe_common import ProbeError
    try:
        from apps.operations.cloud_jobs.diagnostics import scheduler_snapshot
    except ImportError:
        raise ProbeError("scheduler_progress_contract_missing") from None
    deadline = time.monotonic() + 185
    while True:
        try:
            return verify(scheduler_snapshot())
        except ProbeError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(3)


def check(name):
    from probe_integrations import scanner, email, edge
    from probe_services import worker, live
    from probe_storage import storage
    functions = {"database": database, "runtime": runtime, "worker": worker,
                 "scheduler": scheduler, "live": live, "scanner": scanner,
                 "storage": storage, "edge": edge, "email": email}
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    return functions[name]()


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        print(check(sys.argv[2]))
        return
    extra = set(filter(None, os.environ.get("SPACEWORKS_INSTALLER_REQUIRED_PROBES", "").split(",")))
    if not extra <= {"scanner", "email"}:
        sys.exit("Full-host diagnostics refused unknown required probe selection.")
    failed = False
    # Each check runs as a script, whose path entry is the capsule directory, not the
    # application. The full image sets no PYTHONPATH, so pass the working directory on.
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join(
        filter(None, (os.getcwd(), os.environ.get("PYTHONPATH", ""))))}
    for name, allowed in ALLOWED.items():
        try:
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--check", name],
                                    capture_output=True, timeout=210 if name == "scheduler" else 90,
                                    env=environment)
            value = result.stdout.decode("ascii").strip()
            ok = result.returncode == 0 and value in allowed
            if name in extra and value in {"explicitly_disabled", "not_selected_configure_and_test_in_control"}:
                ok = False
            status = value if ok else "failed"
        except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
            ok, status = False, "failed_or_timed_out"
        if not ok:
            failed = True
        print(json.dumps({name: status}), flush=True)
    if failed:
        sys.exit("Required full-host diagnostics failed; installation is incomplete. Check the named service/configuration and retry.")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        main()
    except Exception:
        sys.exit("Full-host diagnostic failed; inspect the selected runtime capability. No provider details were logged.")
