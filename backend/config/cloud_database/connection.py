"""One libpq contract; connection URLs and driver errors never become diagnostics."""

from contextlib import contextmanager
from dataclasses import dataclass, field
import ipaddress
import os

import psycopg2
from psycopg2.extensions import parse_dsn


class DatabaseConfigurationError(RuntimeError):
    code = "database_configuration_invalid"


@dataclass(frozen=True)
class DatabaseSpec:
    parameters: dict = field(repr=False)
    mode: str

    def kwargs(self):
        return dict(self.parameters)


def _local(host):
    if host.startswith("/") or host in {"localhost", "db", "postgres", ""}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_transport(parameters, mode, *, managed=False):
    if mode not in {"direct", "session"}:
        raise DatabaseConfigurationError(
            "Transaction pooling is unsupported. Use a direct endpoint or the "
            "provider's session pooler (Supabase port 5432, not 6543)."
        )
    host = parameters.get("host", "").lower()
    try:
        port = int(parameters.get("port", 5432))
    except (ValueError, TypeError):
        raise DatabaseConfigurationError("PostgreSQL port is invalid.") from None
    if not 1 <= port <= 65535 or "," in host or "," in str(parameters.get("port", "")):
        raise DatabaseConfigurationError("Use one explicit PostgreSQL primary endpoint.")
    supabase = host.endswith((".supabase.co", ".supabase.com", ".supabase.net"))
    if (host.endswith(".neon.tech") and "-pooler" in host.split(".")[0]) or (
        supabase and port == 6543
    ):
        raise DatabaseConfigurationError(
            "This endpoint uses transaction pooling, which backups, migrations and advisory locks cannot use. "
            "Set DATABASE_URL (and SPACEWORKS_MAINTENANCE_DATABASE_URL) to the provider's direct or session "
            "connection string (Supabase: direct host or session pooler on 5432; Neon: the host without -pooler)."
        )
    if supabase and ".pooler." in host and (port != 5432 or mode != "session"):
        raise DatabaseConfigurationError("Supabase shared pooler requires declared session mode on 5432.")
    if managed and not _local(host):
        if parameters.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
            raise DatabaseConfigurationError("Remote managed PostgreSQL requires explicit TLS.")
    for key in ("dbname", "user"):
        if not parameters.get(key):
            raise DatabaseConfigurationError("PostgreSQL database and principal must be explicit.")
    # Libpq service files, environment overrides and arbitrary session options must
    # not redirect an otherwise validated endpoint or change its role/search path.
    allowed = {
        "host", "port", "dbname", "user", "password", "sslmode", "sslrootcert",
        "sslcert", "sslkey", "sslcrl", "sslcrldir", "channel_binding",
        "connect_timeout", "application_name", "options",
        "client_encoding",
    }
    if set(parameters) - allowed:
        raise DatabaseConfigurationError("Unsupported PostgreSQL connection option.")
    if not host:
        raise DatabaseConfigurationError("PostgreSQL endpoint must be explicit.")


def database_spec(url, *, mode=None, managed=False, environ=None, statement_timeout_ms=30000):
    source = os.environ if environ is None else environ
    allowed_pg = {"PGSSLMODE", "PGSSLROOTCERT", "PGSSLCERT", "PGSSLKEY", "PGSSLCRL", "PGCHANNELBINDING", "PGCONNECT_TIMEOUT"}
    if managed and any(name.upper().startswith("PG") and name.upper() not in allowed_pg for name in source):
        raise DatabaseConfigurationError("Remove inherited libpq overrides; configure the validated database URL/TLS fields.")
    mode = mode if mode is not None else source.get("DATABASE_CONNECTION_MODE", "direct" if not managed else "")
    try:
        parameters = parse_dsn(url)
    except Exception:
        raise DatabaseConfigurationError("PostgreSQL connection configuration is invalid.") from None
    # libpq's environment names (channel_binding is PGCHANNELBINDING, no underscore).
    for name, variable in (("sslmode", "PGSSLMODE"), ("sslrootcert", "PGSSLROOTCERT"),
                           ("sslcert", "PGSSLCERT"), ("sslkey", "PGSSLKEY"),
                           ("sslcrl", "PGSSLCRL"), ("channel_binding", "PGCHANNELBINDING")):
        if name not in parameters and source.get(variable):
            parameters[name] = source[variable]
    if parameters.get("options"):
        raise DatabaseConfigurationError("Pass timeouts through the validated builder, not URL options.")
    try:
        connect_timeout = int(parameters.get("connect_timeout", source.get("PGCONNECT_TIMEOUT", 5)))
        statement_timeout_ms = int(statement_timeout_ms)
    except (ValueError, TypeError):
        raise DatabaseConfigurationError("PostgreSQL timeouts must be integers.") from None
    if not 1 <= connect_timeout <= 30 or not 1 <= statement_timeout_ms <= 3600000:
        raise DatabaseConfigurationError("PostgreSQL timeouts exceed supported bounds.")
    validate_transport(parameters, mode, managed=managed)
    parameters["connect_timeout"] = connect_timeout
    parameters["application_name"] = "spaceworks"
    parameters["options"] = f"-c statement_timeout={statement_timeout_ms}"
    return DatabaseSpec(parameters, mode)


def django_database_spec(using="default"):
    from django.conf import settings
    from django.db import connections

    wrapper = connections[using]
    parameters = wrapper.get_connection_params()
    # Django-only options are not valid libpq parameters.
    parameters.pop("cursor_factory", None)
    parameters.pop("context", None)
    mode = getattr(settings, "DATABASE_CONNECTION_MODE", os.environ.get("DATABASE_CONNECTION_MODE", "direct"))
    managed = getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", os.environ.get("SPACEWORKS_DEPLOYMENT_MODE", "host")) == "managed"
    validate_transport(parameters, mode, managed=managed)
    return DatabaseSpec(parameters, mode)


@contextmanager
def connect_database(spec, *, autocommit=True):
    """Close the physical connection on every exit, including failed COMMIT."""
    database = None
    try:
        try:
            database = psycopg2.connect(**spec.kwargs())
            database.autocommit = autocommit
        except Exception:
            raise DatabaseConfigurationError("PostgreSQL connection failed; verify connectivity and privileges.") from None
        yield database
    finally:
        if database is not None:
            database.close()
