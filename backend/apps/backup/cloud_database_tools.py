"""Validated transports for legacy database dictionaries and fixed client argv."""
from pathlib import Path
import subprocess

from django.conf import settings

from config.cloud_database import DatabaseSpec
from config.cloud_database.connection import validate_transport
from config.cloud_database.subprocess import postgres_environment
from .postgres_client import run_client


def configuration_spec(database, *, name=None):
    parameters = {"dbname": name or database["NAME"], "user": database.get("USER", ""),
                  "password": database.get("PASSWORD", ""), "host": database.get("HOST", ""),
                  "port": database.get("PORT") or 5432, **database.get("OPTIONS", {})}
    parameters.setdefault("connect_timeout", 5)
    mode = getattr(settings, "DATABASE_CONNECTION_MODE", "direct")
    validate_transport(parameters, mode, managed=settings.SPACEWORKS_DEPLOYMENT_MODE == "managed")
    return DatabaseSpec(parameters, mode)


def fixed_command(command, *, database=None, extra_env=None, cwd=None, timeout=3600):
    database = database or settings.DATABASES["default"]
    tool = Path(command[0]).name
    args = command[1:]
    if tool in {"pg_dump", "pg_restore", "createdb", "dropdb", "psql"}:
        # Only the old, fixed internal callers may choose another DB name.
        target = next((arg.split("=", 1)[1] for arg in args if arg.startswith("--dbname=")), None)
        args = [arg for arg in args if not arg.startswith("--dbname=")]
        return run_client(tool, args, spec=configuration_spec(database, name=target), timeout=timeout)
    # Scratch migrations use a Python argv, with credentials only in protected env.
    with postgres_environment(configuration_spec(database)) as (_, environment):
        environment.update(extra_env or {})
        try:
            return subprocess.run(command, env=environment, cwd=cwd, timeout=timeout,
                                  check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except (OSError, subprocess.SubprocessError):
            raise RuntimeError("Scratch migration failed; verify schema, privileges and TLS.") from None
