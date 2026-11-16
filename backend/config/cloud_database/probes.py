"""Live transport/extension probes with safe, endpoint-free diagnostics."""

import secrets

from psycopg2 import sql

from .connection import DatabaseConfigurationError, connect_database


def probe_session_transport(spec):
    """Declaration + known-endpoint validation is required in addition to this test.

    A stable PID alone is not proof. The second concurrent connection must fail to
    acquire the first session's lock across multiple committed transactions.
    """
    key = (734_324, secrets.randbelow(2**31 - 1))
    with connect_database(spec) as first, connect_database(spec) as second:
        with first.cursor() as one, second.cursor() as two:
            one.execute("SELECT pg_backend_pid(), pg_try_advisory_lock(%s, %s)", list(key))
            pid, acquired = one.fetchone()
            if not acquired:
                raise DatabaseConfigurationError("PostgreSQL session transport probe could not acquire its test lock.")
            try:
                for _ in range(3):
                    one.execute("BEGIN")
                    one.execute("SELECT pg_backend_pid()")
                    if one.fetchone()[0] != pid:
                        raise DatabaseConfigurationError("PostgreSQL transport changed backends between transactions.")
                    one.execute("COMMIT")
                    two.execute("SELECT pg_try_advisory_lock(%s, %s)", list(key))
                    if two.fetchone()[0]:
                        two.execute("SELECT pg_advisory_unlock(%s, %s)", list(key))
                        raise DatabaseConfigurationError("PostgreSQL transport did not retain session exclusion.")
            finally:
                one.execute("SELECT pg_backend_pid(), pg_advisory_unlock(%s, %s)", list(key))
                if one.fetchone() != (pid, True):
                    raise DatabaseConfigurationError("PostgreSQL transport could not release its retained lock.")
    return {"session_transport": "verified", "declared_mode": spec.mode}


def probe_extensions(cursor):
    cursor.execute("SELECT e.extname, n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname IN ('pgcrypto', 'pg_trgm')")
    extensions = dict(cursor.fetchall())
    if set(extensions) != {"pgcrypto", "pg_trgm"} or any(value not in {"public", "extensions"} for value in extensions.values()):
        raise DatabaseConfigurationError("Required extensions pgcrypto/pg_trgm are missing or use an unapproved schema.")
    cursor.execute(sql.SQL("SELECT encode({}.digest(%s::bytea, 'sha256'::text), 'hex')").format(sql.Identifier(extensions["pgcrypto"])), [b"spaceworks"])
    import hashlib

    if cursor.fetchone()[0] != hashlib.sha256(b"spaceworks").hexdigest():
        raise DatabaseConfigurationError("PostgreSQL cryptographic extension probe failed.")
    return {"extensions": "verified", "pgcrypto_schema": extensions["pgcrypto"]}
