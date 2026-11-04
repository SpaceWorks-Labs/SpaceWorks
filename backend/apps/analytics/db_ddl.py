"""DDL steps of the analytics sync, each idempotent, run as the migrating (owner) role.

Kept apart from the orchestration in ``db_sync`` so every statement that touches roles,
schemas and grants is in one reviewable place. Identifiers are quoted with ``q``; no value
from a request ever reaches these statements.
"""

from apps.tenant_rls.sql import FUNCTION_NAMES as RLS_FUNCTIONS

from .catalogue.types import q
from .db_functions import DROP_LOGIN, ENSURE_LOGIN, FUNCTIONS
from .db_names import ADMIN_SCHEMA, FIXED_GROUP, PLATFORM_SCHEMA, SPACE_SCHEMA

VIEW_SCHEMAS = (SPACE_SCHEMA, PLATFORM_SCHEMA)


def role_exists(cursor, name):
    cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", [name])
    return cursor.fetchone()[0]


def privileges(cursor):
    """(superuser, can create roles, server version number) of the migrating role."""
    cursor.execute("SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname = current_user")
    superuser, createrole = cursor.fetchone()
    cursor.execute("SELECT current_setting('server_version_num')::int")
    return bool(superuser), bool(createrole), cursor.fetchone()[0]


def ensure_roles(cursor, names, *, superuser):
    """Create the NOLOGIN group, owner and reader roles; True when the fixed group is new."""
    created_fixed = False
    if not role_exists(cursor, FIXED_GROUP):
        cursor.execute(f"CREATE ROLE {q(FIXED_GROUP)} NOLOGIN NOINHERIT NOBYPASSRLS")
        created_fixed = True
    for key in ("owner", "powner", "reader", "preader"):
        if not role_exists(cursor, names[key]):
            cursor.execute(f"CREATE ROLE {q(names[key])} NOLOGIN INHERIT NOBYPASSRLS NOSUPERUSER")
    cursor.execute(f"GRANT {q(FIXED_GROUP)} TO {q(names['owner'])}")
    if not superuser:
        # PG16+: the migrating role may act as an owner (SET) but never inherits it, so the
        # fixed-role policy can never apply to the role that owns the tables.
        for key in ("owner", "powner"):
            cursor.execute(f"GRANT {q(names[key])} TO CURRENT_USER WITH INHERIT FALSE, SET TRUE")
    return created_fixed


def ensure_schemas(cursor, names):
    for schema in (*VIEW_SCHEMAS, ADMIN_SCHEMA):
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {q(schema)}")
        cursor.execute(f"REVOKE ALL ON SCHEMA {q(schema)} FROM PUBLIC")
    for key in ("owner", "powner"):
        cursor.execute(f"GRANT USAGE, CREATE ON SCHEMA {q(SPACE_SCHEMA)} TO {q(names[key])}")
    cursor.execute(f"GRANT USAGE, CREATE ON SCHEMA {q(PLATFORM_SCHEMA)} TO {q(names['powner'])}")
    cursor.execute(f"GRANT USAGE ON SCHEMA {q(SPACE_SCHEMA)} TO {q(names['reader'])}")
    cursor.execute(f"GRANT USAGE ON SCHEMA {q(PLATFORM_SCHEMA)} TO {q(names['preader'])}")


def grant_base(cursor, names):
    """View owners read the tables (they cannot log in); every analytics role may call
    L8's policy functions (managed installs revoke function EXECUTE from PUBLIC)."""
    for key in ("owner", "powner"):
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {q(names[key])}")
        cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {q(names[key])}")
    cursor.execute(
        "SELECT p.oid::regprocedure::text FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' AND p.proname = ANY(%s)", [list(RLS_FUNCTIONS)])
    for (signature,) in cursor.fetchall():
        for key in ("owner", "powner", "reader", "preader"):
            cursor.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {q(names[key])}")


def ensure_functions(cursor, callers):
    for statement in FUNCTIONS:
        cursor.execute(statement)
    for signature in (ENSURE_LOGIN, DROP_LOGIN):
        cursor.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        for role in callers:
            cursor.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {q(role)}")
    for role in callers:
        cursor.execute(f"GRANT USAGE ON SCHEMA {q(ADMIN_SCHEMA)} TO {q(role)}")


def drop_view_schemas(cursor):
    """Drop both view schemas with every view in them. The schemas belong to the migrating
    role, and a schema's owner may drop it with its contents even where the views belong
    to the NOLOGIN view owners (which the migrating role deliberately does not inherit)."""
    for schema in VIEW_SCHEMAS:
        cursor.execute(f"DROP SCHEMA IF EXISTS {q(schema)} CASCADE")


def create_view(cursor, schema, name, sql, owner, reader):
    target = f"{q(schema)}.{q(name)}"
    cursor.execute(f"CREATE VIEW {target} WITH (security_barrier = true) AS {sql}")
    cursor.execute(f"REVOKE ALL ON {target} FROM PUBLIC")
    cursor.execute(f"GRANT SELECT ON {target} TO {q(reader)}")
    cursor.execute(f"ALTER VIEW {target} OWNER TO {q(owner)}")


def read_fingerprint(cursor):
    cursor.execute(
        "SELECT obj_description(oid, 'pg_namespace') FROM pg_namespace WHERE nspname = %s", [SPACE_SCHEMA])
    row = cursor.fetchone()
    return row[0] if row else None


def write_fingerprint(cursor, fingerprint):
    cursor.execute(f"COMMENT ON SCHEMA {q(SPACE_SCHEMA)} IS %s", [fingerprint])


def owners_intact(cursor, names, expected):
    """Every expected view exists with its expected owner (a restore resets owners)."""
    cursor.execute(
        "SELECT n.nspname, c.relname, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind = 'v' AND n.nspname = ANY(%s)",
        [list(VIEW_SCHEMAS)])
    live = {(schema, name): owner for schema, name, owner in cursor.fetchall()}
    cursor.execute("SELECT to_regprocedure(%s) IS NOT NULL", [ENSURE_LOGIN])
    return cursor.fetchone()[0] and live == {key: names[owner] for key, owner in expected.items()}
