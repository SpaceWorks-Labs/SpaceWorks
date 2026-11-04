"""Host-only privileged targeting: pointer selects a database, never credentials."""

import re
import uuid
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from .database_identity import query_live_database_identity
from .host_marker import MarkerStage

def database_name(url):
    from urllib.parse import parse_qsl
    parsed = urlsplit(url)
    name = unquote(parsed.path.lstrip("/"))
    if (parsed.scheme not in {"postgres", "postgresql"} or not name or "\x00" in name or "/" in name
            or parsed.fragment or any(key in {"dbname", "database", "service", "passfile"} for key, _ in parse_qsl(parsed.query))):
        raise ValueError("The admitted runtime database pointer is invalid.")
    return name


def privileged_url(maintenance_url, runtime_url):
    """Replace only dbname, retaining maintenance principal, endpoint and TLS."""
    name = database_name(runtime_url)
    parsed = urlsplit(maintenance_url)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise ValueError("The privileged database connection is invalid.")
    # Reject alternate libpq routing in the query instead of allowing it to
    # override the path selected by the protected runtime pointer.
    from urllib.parse import parse_qsl
    if any(key in {"dbname", "database", "host", "hostaddr", "port", "user", "password", "service", "passfile"}
           for key, _ in parse_qsl(parsed.query)):
        raise ValueError("Privileged database routing overrides are refused.")
    return urlunsplit((parsed.scheme, parsed.netloc, "/" + quote(name, safe=""), parsed.query, ""))


def expected_target(environ):
    values = (environ.get("SPACEWORKS_PRIVILEGED_TARGET_NAME", ""),
              environ.get("SPACEWORKS_PRIVILEGED_TARGET_OID", ""),
              environ.get("SPACEWORKS_PRIVILEGED_TARGET_UUID", ""))
    required = environ.get("SPACEWORKS_PRIVILEGED_TARGET_REQUIRED", "")
    if required not in {"", "0", "1"}:
        raise ValueError("The privileged target requirement is invalid.")
    if not any(values) and required != "1":
        return None
    name, oid, identity = values
    try:
        if not name or not re.fullmatch(r"[1-9][0-9]*", oid) or not 0 < int(oid) < 2**32:
            raise ValueError
        if str(uuid.UUID(identity)) != identity:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValueError("The protected privileged target tuple is incomplete or invalid.") from None
    return name, int(oid), identity


def verify_target(database, marker, runtime_url, environ, *, allow_initial=False):
    """Run before grants/DDL. Only an explicitly unbound bootstrap may lack UUID."""
    expected = expected_target(environ)
    selected = database_name(runtime_url)
    with database.cursor() as cursor:
        cursor.execute("SELECT current_database(), oid FROM pg_database WHERE datname=current_database()")
        name, oid = cursor.fetchone()
        if name != selected:
            raise ValueError("Privileged target disagrees with the runtime pointer.")
        if marker is not None:
            if marker.stage != MarkerStage.BOUND or (marker.database.name, marker.database.oid) != (name, oid):
                raise ValueError("Privileged target disagrees with the protected marker.")
        cursor.execute("SELECT to_regclass('public.backup_deploymentdatabaseidentity')")
        has_identity = cursor.fetchone()[0] is not None
        if marker is None:
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p'))")
            if cursor.fetchone()[0] and (name, str(oid)) != (
                    environ.get("SPACEWORKS_INITIALIZE_DATABASE_NAME"),
                    environ.get("SPACEWORKS_INITIALIZE_DATABASE_OID")):
                raise ValueError("A populated database needs the proven legacy initialization admission.")
    if not has_identity:
        if expected is not None or not allow_initial or (marker and marker.database.server_identity is not None):
            raise ValueError("The privileged target identity is unavailable.")
        return None
    live = query_live_database_identity(database)
    if marker is not None and marker.database.server_identity is not None:
        if live.database_uuid != marker.database.server_identity["database_uuid"]:
            raise ValueError("Privileged database UUID disagrees with the protected marker.")
        system_identifier = marker.database.server_identity.get("system_identifier")
        if system_identifier is not None and getattr(live, "system_identifier", None) != system_identifier:
            raise ValueError("Privileged server identity disagrees with the protected marker.")
    elif not allow_initial:
        raise ValueError("The protected marker lacks a database UUID.")
    if expected is not None and expected != (name, int(oid), live.database_uuid):
        raise ValueError("Privileged target disagrees with the protected expected tuple.")
    return live
