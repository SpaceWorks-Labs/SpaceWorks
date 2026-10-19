"""App-only grants for shared provider projects; no provider schema access."""

from psycopg2 import sql

from apps.backup.database_grants import DatabaseGrantError, _assert_narrow_runtime_role
from .data_api import data_api_roles, revoke_data_api_access
from .function_grants import grant_application_functions


def apply_managed_grants(cursor, runtime_role, tables):
    """Maintenance job supplies registered Django tables after migrations."""
    cursor.execute("SELECT current_user, current_database()")
    owner, database = cursor.fetchone()
    if owner == runtime_role:
        raise DatabaseGrantError("Maintenance and runtime principals must be distinct.")
    _assert_narrow_runtime_role(cursor, runtime_role)
    role = sql.Identifier(runtime_role)
    cursor.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC, {}").format(role))
    cursor.execute(sql.SQL("REVOKE CREATE ON DATABASE {} FROM PUBLIC, {}").format(sql.Identifier(database), role))
    cursor.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), role))
    cursor.execute(sql.SQL("GRANT TEMPORARY ON DATABASE {} TO {}").format(sql.Identifier(database), role))
    cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
    for table in sorted(set(tables)):
        revoke_data_api_access(cursor, table)
        cursor.execute(sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(sql.Identifier(table), role))
        cursor.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{} TO {}").format(sql.Identifier(table), role))
        cursor.execute(
            "SELECT pg_get_serial_sequence(format('public.%%I', %s), attname) "
            "FROM pg_attribute WHERE attrelid = format('public.%%I', %s)::regclass "
            "AND attnum > 0 AND NOT attisdropped", [table, table],
        )
        for sequence, in cursor.fetchall():
            if sequence:
                cursor.execute("SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=%s::regclass", [sequence])
                schema_name, sequence_name = cursor.fetchone()
                sequence_target = sql.Identifier(schema_name, sequence_name)
                cursor.execute(sql.SQL("REVOKE ALL ON SEQUENCE {} FROM PUBLIC, {}").format(sequence_target, role))
                for denied in data_api_roles(cursor):
                    cursor.execute(sql.SQL("REVOKE ALL ON SEQUENCE {} FROM {}").format(sequence_target, sql.Identifier(denied)))
                cursor.execute(sql.SQL("GRANT USAGE, SELECT, UPDATE ON SEQUENCE {} TO {}").format(sql.Identifier(schema_name, sequence_name), role))
    for privileges, kind in (("SELECT, INSERT, UPDATE, DELETE", "TABLES"), ("USAGE, SELECT, UPDATE", "SEQUENCES"), ("EXECUTE", "FUNCTIONS")):
        cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT " + privileges + " ON " + kind + " TO {}").format(sql.Identifier(owner), role))
    grant_application_functions(cursor, runtime_role)
    # New app tables are owned by the maintenance principal; catalog verification
    # below refuses unknown owner tables before granting them to future processes.


def application_tables(cursor, registered):
    """Fail closed for unclassified app tables, ignore explicitly foreign schemas."""
    registered = set(registered)
    cursor.execute(
        "SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.relkind IN ('r', 'p') AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user) "
        "AND n.nspname NOT IN ('pg_catalog', 'information_schema') "
        "AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp_%'"
    )
    foreign_schemas = {"auth", "storage", "realtime", "supabase_functions", "extensions", "vault", "graphql", "graphql_public"}
    for schema, table in cursor.fetchall():
        if schema in foreign_schemas:
            continue
        if schema != "public" or table not in registered:
            raise DatabaseGrantError("An application-owned table is unclassified; register it before capture or release.")
    return registered
