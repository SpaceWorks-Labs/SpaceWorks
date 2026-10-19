"""Secret-free argv and isolated libpq environment for pg_dump/restore tools."""

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

from .connection import DatabaseConfigurationError


def _escape(value):
    value = str(value)
    if any(character in value for character in "\r\n\x00"):
        raise DatabaseConfigurationError("PostgreSQL passfile values contain invalid characters.")
    return value.replace("\\", "\\\\").replace(":", "\\:")


@contextmanager
def postgres_environment(spec, *, environ=None):
    """Yield argv connection flags + env; remove all inherited PG* configuration."""
    parameters = spec.kwargs()
    environment = {
        key: value for key, value in (os.environ if environ is None else environ).items()
        if not key.upper().startswith("PG")
    }
    descriptor, filename = tempfile.mkstemp(prefix="spaceworks-pgpass-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            os.chmod(filename, 0o600)
            values = [parameters.get(key, "") for key in ("host", "port", "dbname", "user", "password")]
            values[1] = values[1] or 5432
            stream.write(":".join(map(_escape, values)) + "\n")
        environment["PGPASSFILE"] = filename
        # libpq environment names; two differ from "PG" + upper(parameter).
        renamed = {"channel_binding": "PGCHANNELBINDING", "application_name": "PGAPPNAME"}
        for name in ("sslmode", "sslrootcert", "sslcert", "sslkey", "sslcrl", "sslcrldir", "channel_binding", "connect_timeout", "options", "application_name"):
            if name in parameters:
                environment[renamed.get(name, "PG" + name.upper())] = str(parameters[name])
        arguments = []
        for key, flag in (("host", "--host"), ("port", "--port"), ("dbname", "--dbname"), ("user", "--username")):
            if key in parameters:
                arguments.extend([flag, str(parameters[key])])
        arguments.append("--no-password")
        yield arguments, environment
    finally:
        Path(filename).unlink(missing_ok=True)
