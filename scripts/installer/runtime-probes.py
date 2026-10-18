#!/usr/bin/env python3
"""Core full-host completion checks. Never sends mail or runs domain jobs."""
import json
import os
import shutil
import socket
import subprocess
import sys


class ProbeError(Exception):
    def __init__(self, code):
        self.code = code


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    statuses = {}
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
    statuses["database"] = "runtime_nonowner_no_pending_migrations"
    for binary in ("age", "age-keygen", "ffprobe", "ffmpeg"):
        if not shutil.which(binary):
            raise ProbeError("missing_runtime_binary")
    subprocess.run([sys.executable, "-m", "scripts.verify_printable_runtime", "--bundle"],
                   check=True, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    statuses["runtime"] = "binaries_and_printable_bundle_verified"
    policy = getattr(settings, "UPLOAD_SCAN_POLICY", "none")
    if policy == "clamav":
        with socket.create_connection((settings.CLAMD_HOST, settings.CLAMD_PORT), timeout=5) as peer:
            peer.settimeout(5)
            peer.sendall(b"zVERSION\0")
            response = peer.recv(1024)
            if not response.startswith(b"ClamAV ") or b"/" not in response:
                raise ProbeError("scanner_version_unavailable")
        statuses["scanner"] = "reachable_version_reported"
    elif policy == "none":
        statuses["scanner"] = "explicitly_disabled"
    else:
        raise ProbeError("invalid_scan_policy")
    print(json.dumps(statuses, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except ProbeError as error:
        sys.exit(f"Full-host runtime verification failed [{error.code}]; installation is incomplete.")
    except Exception:
        sys.exit("Full-host runtime verification failed; inspect readiness and the selected runtime capabilities. Installation is incomplete.")
