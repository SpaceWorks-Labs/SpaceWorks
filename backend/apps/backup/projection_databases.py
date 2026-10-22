"""Short-lived PostgreSQL databases used to derive and verify readable mains."""

from contextlib import contextmanager
import logging
import subprocess
import uuid

from django.conf import settings
from django.db import connections

from apps.backup.postgres_client import (
    PostgresClientUnavailable,
    client_binary,
    server_major,
)
from apps.backup.recipient_selection import BackupBuildError

logger = logging.getLogger(__name__)


def _client(tool, major=None):
    """Resolve a client binary, as a backup build failure when it is missing."""
    try:
        return client_binary(tool, major)
    except PostgresClientUnavailable as exc:
        raise BackupBuildError(str(exc)) from exc


def _run(command):
    from .cloud_database_tools import fixed_command
    try:
        return fixed_command(command)
    except Exception:
        raise BackupBuildError("The readable-main database operation failed; verify TLS, privileges and client major.") from None


@contextmanager
def temporary_database(role):
    name = f"spaceworks_backup_{role}_{uuid.uuid4().hex}"[:63]
    alias = f"backup_{role}_{uuid.uuid4().hex}"
    major = server_major()
    _run([_client("createdb", major), name])
    connections.databases[alias] = {
        **settings.DATABASES["default"],
        "NAME": name,
        "CONN_MAX_AGE": 0,
    }
    try:
        yield alias, name
    finally:
        connection = connections[alias]
        connection.close()
        del connections.databases[alias]
        if hasattr(connections._connections, alias):
            delattr(connections._connections, alias)
        _run([_client("dropdb", major), "--if-exists", name])


def restore_dump(path, database_name):
    _run([
        _client("pg_restore"),
        "--exit-on-error",
        "--no-owner",
        "--no-acl",
        f"--dbname={database_name}",
        str(path),
    ])


def dump_database(database_name, destination):
    _run([
        _client("pg_dump"),
        "--format=custom",
        "--no-owner",
        "--no-acl",
        f"--dbname={database_name}",
        f"--file={destination}",
    ])
