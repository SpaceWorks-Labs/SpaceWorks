"""DDL steps of the analytics sync, each idempotent, run as the migrating (owner) role.

Kept apart from the orchestration in ``db_sync`` so every statement that touches roles,
schemas and grants is in one reviewable place. Identifiers are quoted with ``q``; no value
from a request ever reaches these statements.
"""

from apps.tenant_rls.sql import FUNCTION_NAMES as RLS_FUNCTIONS

from .catalogue.types import q
from .db_functions import DROP_LOGIN, ENSURE_LOGIN, FUNCTIONS
from .db_names import ADMIN_SCHEMA, FIXED_GROUP, PLATFORM_SCHEMA, SPACE_SCHEMA
from .migration_acl import as_role
from .migration_views import _options

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
    """Compatibility hook for pre_migrate/sync: deliberately perform no DDL.

    Column ALTERs suspend their exact dependency closure inside each migration's
    transaction (migration_support). Sync replaces compatible definitions in place.
    Dropping here would precede that capture and destroy custom/external objects.
    Keep the schemas themselves, including their ACLs and default privileges.
    Historical migration tests use their own explicit suspend/restore teardown.
    """


def create_view(cursor, schema, name, sql, owner, reader):
    target = f"{q(schema)}.{q(name)}"
    cursor.execute("SELECT pg_get_userbyid(relowner),relkind,reloptions FROM pg_class WHERE oid=to_regclass(%s)", [target])
    existing = cursor.fetchone()
    if existing and existing[:2] != (owner, 'v'):
        raise RuntimeError(f"Cannot replace analytics view with unexpected owner/kind: {target} {existing!r}")
    with as_role(cursor, q, owner):
        if existing:
            # Explicitly retain options: CREATE OR REPLACE resets omitted options.
            # PostgreSQL keeps the OID, ACLs, comments, rules and triggers.
            # An incompatible output shape fails atomically rather
            # than deleting dependents; sync's existing failed-view report records it.
            options = _options(cursor, q, existing[2])
            cursor.execute(f"CREATE OR REPLACE VIEW {target}{options} AS {sql}")
            return
        cursor.execute(f"CREATE VIEW {target} WITH (security_barrier = true) AS {sql}")
        cursor.execute(
            "SELECT DISTINCT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END "
            "FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE c.oid=to_regclass(%s)", [target],
        )
        grantees = [role for (role,) in cursor.fetchall()]
        for role in dict.fromkeys(['PUBLIC', owner, *grantees]):
            recipient = 'PUBLIC' if role == 'PUBLIC' else q(role)
            cursor.execute(f"REVOKE ALL ON TABLE {target} FROM {recipient} CASCADE")
        cursor.execute(f"GRANT ALL ON TABLE {target} TO {q(owner)}")
        cursor.execute(f"GRANT SELECT ON TABLE {target} TO {q(reader)}")


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
    # Custom views are not catalogue entries and must not force a destructive rebuild.
    return cursor.fetchone()[0] and all(live.get(key) == names[owner] for key, owner in expected.items())
