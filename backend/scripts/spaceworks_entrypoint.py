#!/usr/bin/env python3
"""Common fail-closed image entrypoint for every SpaceWorks process role."""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.backup.host_marker import MarkerError, read_marker
from apps.backup.process_roles import ProcessRole, admission_for
from apps.backup.entrypoint_capability import consume_entrypoint_capability
from apps.backup.managed.profile import deployment_profile, effective_environment, validate_process


def refuse(detail):
    print(f"SpaceWorks entrypoint refused startup: {detail}", file=sys.stderr)
    return 78


def parse_invocation(argv):
    if len(argv) < 4 or argv[1] != "--role" or not argv[3:]:
        raise ValueError("an explicit --role and command are required")
    try:
        role = ProcessRole(argv[2])
    except ValueError as exc:
        raise ValueError("process role is unknown") from exc
    command = argv[3:]
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("process command is missing")
    return role, command


def live_database_identity(database_url):
    from config.cloud_database import connect_database, database_spec
    from apps.backup.managed.mode_binding import assert_mode_binding

    with connect_database(database_spec(database_url)) as database:
        with database.cursor() as cursor:
            assert_mode_binding(cursor, "host")
            cursor.execute(
                "SELECT current_database(), oid FROM pg_database WHERE datname = current_database()"
            )
            return cursor.fetchone()


def request_launch_capability(marker, _live_identity):
    return consume_entrypoint_capability(marker, os.environ["DATABASE_URL"])


def main(argv=None, *, capability_request=request_launch_capability):
    argv = argv or sys.argv
    try:
        role, command = parse_invocation(argv)
        profile = deployment_profile()
        validate_process(profile, role, command)
        if profile.mode == "managed":
            from apps.backup.managed.entrypoint import admit_managed_command

            admit_managed_command(role, command)
            os.environ.update(effective_environment(os.environ))
            os.execvp(command[0], command)
            return 0
        marker = read_marker(
            os.environ.get(
                "SPACEWORKS_HOST_MARKER_PATH",
                "/run/spaceworks-host/restore-marker.json",
            )
        )
    except (ValueError, MarkerError) as exc:
        return refuse(str(exc))
    except Exception:
        return refuse("managed launch configuration or database admission failed")
    admission = admission_for(marker.state, role)
    if not admission.admitted:
        return refuse(admission.reason)
    try:
        bound_database = marker.require_bound_database()
    except MarkerError as exc:
        return refuse(str(exc))
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return refuse("DATABASE_URL is missing")
    if role == ProcessRole.MIGRATE:
        try:
            from apps.backup.privileged_target import privileged_url, verify_target
            from config.cloud_database import connect_database, database_spec
            runtime_url = os.environ.get("SPACEWORKS_RUNTIME_DATABASE_URL", "")
            database_url = privileged_url(database_url, runtime_url)
            with connect_database(database_spec(database_url)) as database:
                verify_target(database, marker, runtime_url, os.environ,
                              allow_initial=bound_database.server_identity is None)
            os.environ["DATABASE_URL"] = database_url
        except Exception:
            return refuse("privileged migration target could not be verified")
    try:
        identity = live_database_identity(database_url)
    except Exception:
        return refuse("live database identity could not be verified")
    if identity != (bound_database.name, bound_database.oid):
        return refuse("live database identity disagrees with the host marker")
    # Role denial above is deliberately before capability parsing. The live identity
    # is also established first so H1b can send it to the host for independent matching.
    if admission.requires_capability:
        try:
            capability_request(marker, identity)
        except Exception as exc:
            return refuse(f"launch capability was not granted: {exc}")
    os.execvp(command[0], command)


if __name__ == "__main__":
    raise SystemExit(main())
