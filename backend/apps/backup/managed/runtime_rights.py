"""Positive and negative SQL proofs for the separate managed runtime principal."""

from psycopg2 import sql

from apps.backup.database_grants import DatabaseGrantError


def grant_required_extensions(cursor, runtime_role):
    cursor.execute(
        "SELECT n.nspname, p.proname, pg_get_function_identity_arguments(p.oid) "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "JOIN pg_depend d ON d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.deptype='e' "
        "JOIN pg_extension e ON e.oid=d.refobjid WHERE e.extname IN ('pgcrypto', 'pg_trgm')"
    )
    functions = cursor.fetchall()
    if any(schema not in {"public", "extensions"} for schema, _name, _args in functions):
        raise DatabaseGrantError("Required extension functions use an unapproved schema.")
    for schema, name, arguments in functions:
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema), sql.Identifier(runtime_role)))
        target = sql.SQL("{}({})").format(sql.Identifier(schema, name), sql.SQL(arguments))
        cursor.execute(sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(target, sql.Identifier(runtime_role)))


def prove_runtime_rights(cursor, tables):
    for table in sorted(tables):
        cursor.execute(
            "SELECT has_table_privilege(current_user, format('public.%%I', %s), 'SELECT') "
            "AND has_table_privilege(current_user, format('public.%%I', %s), 'INSERT') "
            "AND has_table_privilege(current_user, format('public.%%I', %s), 'UPDATE') "
            "AND has_table_privilege(current_user, format('public.%%I', %s), 'DELETE'), "
            "has_table_privilege(current_user, format('public.%%I', %s), 'TRUNCATE,REFERENCES,TRIGGER')",
            [table] * 5,
        )
        row = cursor.fetchone()
        # Required rights use AND; the forbidden comma list means ANY privilege.
        if not row[0] or any(row[1:]):
            raise DatabaseGrantError("Managed runtime table privileges are not narrow.")
    cursor.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname IN ('auth', 'storage', 'realtime', 'vault', 'supabase_functions') "
        "AND c.relkind IN ('r','p') AND (has_table_privilege(current_user,c.oid,'SELECT') "
        "OR has_table_privilege(current_user,c.oid,'INSERT') OR has_table_privilege(current_user,c.oid,'UPDATE') "
        "OR has_table_privilege(current_user,c.oid,'DELETE')))"
    )
    if cursor.fetchone()[0]:
        raise DatabaseGrantError("Runtime principal has access to provider-owned tables.")
    return {"runtime_privileges": "verified"}
