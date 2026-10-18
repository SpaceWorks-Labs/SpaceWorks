"""Read-only PG16/17, transport and authority probes on retained connections."""

from contextlib import ExitStack
import hashlib
from urllib.parse import parse_qs, urlsplit
import uuid

from .errors import SetupError


def validate_endpoint(url, mode, provider):
    try:
        parsed = urlsplit(url)
        options = parse_qs(parsed.query, strict_parsing=True)
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname or not parsed.username or not parsed.path.strip("/"):
            raise ValueError
        if options.get("sslmode") not in (["verify-full"], ["require"]):
            raise ValueError
        if any(k in options for k in ("options", "service", "passfile", "host", "hostaddr", "port", "dbname", "user", "password")):
            raise ValueError
        host = parsed.hostname.lower()
        port = parsed.port or 5432
        if mode not in {"direct", "session"} or "-pooler" in host or port == 6543:
            raise SetupError("transaction_pool_refused", "Use a documented direct or session endpoint; Supabase session uses port 5432, Neon uses its direct host.")
        if "pooler.supabase." in host and (mode != "session" or port != 5432):
            raise SetupError("pool_mode_contradiction", "Declare the Supabase IPv4 pooler endpoint as session mode on 5432.")
    except (ValueError, TypeError, AttributeError):
        raise SetupError("database_url_invalid", "Use a protected PostgreSQL URL with explicit sslmode=verify-full (preferred) or require.") from None
    return parsed


def connect(url):
    import psycopg2
    # Explicit kwargs override ambient PGOPTIONS and prevent unbounded probe SQL.
    return psycopg2.connect(url, connect_timeout=5, gssencmode="disable", options="-c statement_timeout=5000 -c lock_timeout=2000", application_name="spaceworks-setup-probe")


def database_probe(values, answers, *, require_identity=True):
    runtime = values.get("DATABASE_URL", "")
    maintenance = values.get("DATABASE_MAINTENANCE_URL", "")
    validate_endpoint(runtime, answers["database_connection_mode"], answers["database_provider"])
    validate_endpoint(maintenance, answers["maintenance_connection_mode"], answers["database_provider"])
    with ExitStack() as stack:
        connections = []
        for url in (runtime, runtime, maintenance):
            db = connect(url)
            stack.callback(db.close)
            connections.append(db)
            db.autocommit = True
        first, contender, owner = connections
        with first.cursor() as cur, contender.cursor() as other, owner.cursor() as privileged:
            cur.execute("SELECT current_setting('server_version_num')::int, pg_is_in_recovery(), current_database(), current_user")
            version, replica, database, runtime_role = cur.fetchone()
            if version // 10000 not in {16, 17} or replica:
                raise SetupError("unsupported_database", "Use a writable PostgreSQL 16 or 17 primary.")
            privileged.execute("SELECT current_database(), current_user")
            target, maintenance_role = privileged.fetchone()
            if target != database or maintenance_role == runtime_role:
                raise SetupError("maintenance_separation", "Use separate maintenance and narrow runtime principals on the same database.")
            cur.execute("SELECT rolsuper, rolinherit, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user")
            if any(cur.fetchone()):
                raise SetupError("runtime_role_privileged", "Provision a NOINHERIT, non-owner runtime role without elevated rights.")
            cur.execute("SELECT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)) OR EXISTS(SELECT 1 FROM pg_database WHERE datdba=(SELECT oid FROM pg_roles WHERE rolname=current_user)) OR EXISTS(SELECT 1 FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)) OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)) OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)) OR has_schema_privilege(current_user,'public','CREATE') OR has_database_privilege(current_database(),'CREATE')")
            if cur.fetchone()[0]:
                raise SetupError("runtime_role_owner", "Remove runtime role memberships, object ownership and schema CREATE before launch.")
            cur.execute("SELECT extname, nspname FROM pg_extension JOIN pg_namespace ON extnamespace=pg_namespace.oid WHERE extname IN ('pg_trgm','pgcrypto')")
            extensions = dict(cur.fetchall())
            if set(extensions) != {"pg_trgm", "pgcrypto"}:
                raise SetupError("database_extensions", "Have maintenance install pg_trgm and pgcrypto in the provider-supported schema.")
            from psycopg2 import sql
            cur.execute(sql.SQL("SELECT {}.digest(%s::bytea, 'sha256')").format(sql.Identifier(extensions["pgcrypto"])), [b"spaceworks-probe"])
            if bytes(cur.fetchone()[0]) != hashlib.sha256(b"spaceworks-probe").digest():
                raise SetupError("database_digest", "Grant the narrow role access to the existing pgcrypto digest function.")
            lock_probe(cur, other)
            # A successful retained-session test corroborates declared provider docs; it
            # cannot turn an undocumented/known transaction pooler into session transport.
            identity = None
            cur.execute("SELECT to_regclass('public.backup_deploymentdatabaseidentity')")
            if cur.fetchone()[0]:
                cur.execute("SELECT database_uuid::text FROM public.backup_deploymentdatabaseidentity WHERE id=1")
                row = cur.fetchone()
                identity = uuid.UUID(row[0]) if row else None
                privileged.execute("SELECT database_uuid::text FROM public.backup_deploymentdatabaseidentity WHERE id=1")
                row = privileged.fetchone()
                if identity and (not row or row[0] != str(identity)):
                    raise SetupError("database_identity_mismatch", "Point both credentials at the same initialized database UUID.")
            if require_identity and not identity:
                raise SetupError("database_identity_missing", "Run the finite release/adoption operation before final verification.")
    tls = parse_qs(urlsplit(runtime).query)["sslmode"][0]
    return {"major": version // 10000, "identity_sha256": hashlib.sha256(identity.bytes).hexdigest() if identity else None, "transport": answers["database_connection_mode"], "tls": tls, "tls_identity": "verified" if tls == "verify-full" else "not-verified-prefer-verify-full", "status": "passed"}


def lock_probe(cur, other):
    key = uuid.uuid4().int % (2**63 - 1)
    cur.execute("SELECT pg_backend_pid(), pg_try_advisory_lock(%s)", [key])
    pid, acquired = cur.fetchone()
    if not acquired:
        raise SetupError("lock_probe_failed", "Retry the retained-session/competing-lock validation.")
    try:
        for _ in range(3):
            cur.execute("BEGIN")
            cur.execute("SELECT pg_backend_pid(), pg_try_advisory_xact_lock(%s)", [key])
            current_pid, nested = cur.fetchone()
            cur.execute("COMMIT")
            other.execute("SELECT pg_try_advisory_lock(%s)", [key])
            if other.fetchone()[0]:
                other.execute("SELECT pg_advisory_unlock(%s)", [key])
                raise SetupError("session_not_retained", "Change to a verified direct/session endpoint before launch.")
            if current_pid != pid or not nested:
                raise SetupError("session_not_retained", "Change to a verified direct/session endpoint before launch.")
    finally:
        cur.execute("ROLLBACK")
        cur.execute("SELECT pg_advisory_unlock(%s)", [key])
        if cur.fetchone()[0] is not True:
            raise SetupError("session_lock_lost", "The probe session lost its lock; verify provider transport before retrying.")
