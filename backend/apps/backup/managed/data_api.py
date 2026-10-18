"""Django's tables are private from provider Data API roles, including old projects."""

from psycopg2 import sql


def data_api_roles(cursor):
    cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated', 'service_role')")
    return [name for name, in cursor.fetchall()]


def prepare_private_defaults(cursor):
    """Before migrations: prevent provider automatic grants exposing new tables."""
    for name in data_api_roles(cursor):
        for kind in ("TABLES", "SEQUENCES", "FUNCTIONS"):
            cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON " + kind + " FROM {}").format(sql.Identifier(name)))
    cursor.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC")


def revoke_data_api_access(cursor, table):
    target = sql.Identifier("public", table)
    cursor.execute(sql.SQL("REVOKE ALL ON TABLE {} FROM PUBLIC").format(target))
    for name in data_api_roles(cursor):
        cursor.execute(sql.SQL("REVOKE ALL ON TABLE {} FROM {}").format(target, sql.Identifier(name)))
