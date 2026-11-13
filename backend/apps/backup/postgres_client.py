"""Choosing the PostgreSQL client binaries that match this deployment's server.

The image ships two client majors deliberately, because the two directions have
opposite constraints:

* ``pg_dump`` must be at least as new as any *source* server tenant migration
  reads (14-17), so the newest client is the one on ``PATH``.
* Anything that dumps or restores *this* deployment has the reverse requirement.
  A custom-format archive written by ``pg_dump`` 17 carries file-header version
  1.16, which ``pg_restore`` 16 refuses outright, and ``pg_restore`` 17+ emits an
  unconditional ``SET transaction_timeout = 0;`` -- a GUC that does not exist
  before 17, so a pre-17 server rejects it and ``--exit-on-error`` aborts.

So the deployment's own backup, restore and readable-main projection all resolve
their client from this module rather than trusting ``PATH``. Getting this wrong
is not a warning: it produces archives the shipped restore path cannot read.
"""

from functools import lru_cache
from pathlib import Path
import re
import shutil
import subprocess

from django.db import connections

# Where a distribution package puts one major version's client binaries.
_VERSIONED_CLIENT_DIRS = (
    "/usr/lib/postgresql/{major}/bin",  # Debian, Ubuntu, PGDG apt
    "/usr/pgsql-{major}/bin",  # RHEL, Rocky, PGDG yum
)


class PostgresClientUnavailable(RuntimeError):
    """No client matching the server's major version is installed."""


def server_major():
    """Major version of the PostgreSQL server this deployment runs on."""
    with connections["default"].cursor() as cursor:
        cursor.execute("SHOW server_version_num")
        return int(cursor.fetchone()[0]) // 10000


@lru_cache(maxsize=None)
def _binary_major(path):
    """Major version a client binary reports, or None when it cannot be read."""
    try:
        completed = subprocess.run(
            [path, "--version"], capture_output=True, check=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"\b(\d+)\.\d+", completed.stdout)
    return int(match.group(1)) if match else None


def client_binary(tool, major=None):
    """Absolute path to `tool` for the server's major version.

    Fails closed rather than falling back to whatever is on PATH: a mismatched
    client does not degrade gracefully, it writes archives the restore path
    cannot read.
    """
    major = server_major() if major is None else major
    if tool not in {"pg_dump", "pg_restore", "psql", "createdb", "dropdb"} or major not in {16, 17}:
        raise PostgresClientUnavailable("Only PostgreSQL 16 and 17 servers are supported: this database reports another major version. Use a PostgreSQL 16 or 17 server (an external provider must be set to 16 or 17).")
    for template in _VERSIONED_CLIENT_DIRS:
        candidate = Path(template.format(major=major)) / tool
        if candidate.is_file() and _binary_major(str(candidate)) == major:
            return str(candidate)
    on_path = shutil.which(tool)
    if on_path and _binary_major(on_path) == major:
        return on_path
    raise PostgresClientUnavailable(
        f"No PostgreSQL {major} client is installed, so {tool} cannot run "
        f"against this deployment's server. Install postgresql-client-{major}; "
        f"the client major must match the database server."
    )


# PostgreSQL client tools inherit nothing else from the web/worker process: no
# DATABASE_URL, SECRET_KEY, storage or provider credentials.
_CLIENT_PARENT_ENV = frozenset({
    "LANG", "LC_ALL", "LC_CTYPE", "PATH", "SSL_CERT_DIR", "SSL_CERT_FILE", "TZ",
})


def run_client(tool, arguments, *, spec, major=None, timeout=3600, binary=None):
    """Shared subprocess boundary: TLS retained, passfile removed, stderr private."""
    from config.cloud_database.subprocess import postgres_environment

    forbidden = {"-d", "--dbname", "-h", "--host", "-p", "--port", "-U", "--username", "--maintenance-db"}
    if any(argument.split("=", 1)[0] in forbidden for argument in arguments):
        raise PostgresClientUnavailable("Pass PostgreSQL connection facts through the validated spec only.")
    # A caller that already resolved the version-matched binary may pass it in.
    binary = binary or client_binary(tool, major)
    # --- lane L8: data dumps read policed tables with row security on (tenant_rls.pg_tools).
    from apps.tenant_rls.pg_tools import client_arguments
    arguments = client_arguments(tool, arguments)
    with postgres_environment(spec) as (connection_args, environment):
        if tool in {"createdb", "dropdb"}:
            connection_args = ["--maintenance-db" if value == "--dbname" else value for value in connection_args]
        # postgres_environment already dropped inherited PG*; it sets only the
        # validated PG* values and the private PGPASSFILE.
        environment = {key: value for key, value in environment.items()
                       if key.startswith("PG") or key in _CLIENT_PARENT_ENV}
        try:
            return subprocess.run(
                [binary, *connection_args, *arguments], env=environment,
                capture_output=True, check=True, timeout=timeout,
            )
        except (OSError, subprocess.SubprocessError):
            raise PostgresClientUnavailable("PostgreSQL client operation failed; check privileges, TLS and archive compatibility.") from None
