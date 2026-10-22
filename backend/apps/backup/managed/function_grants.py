"""Grant exact registered application functions without exposing provider RPCs."""

from psycopg2 import sql

from apps.backup.database_grants import DatabaseGrantError

from .data_api import data_api_roles
from .function_catalog import APPLICATION_FUNCTIONS


def grant_application_functions(cursor, runtime_role):
    cursor.execute(
        "SELECT p.proname, pg_get_function_identity_arguments(p.oid) "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='public' AND p.proowner=(SELECT oid FROM pg_roles WHERE rolname=current_user) "
        "AND p.prokind='f' AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass "
        "AND d.objid=p.oid AND d.deptype='e')"
    )
    functions = cursor.fetchall()
    if any(name not in APPLICATION_FUNCTIONS for name, _arguments in functions):
        raise DatabaseGrantError("An application-owned SQL function is unclassified.")
    denied = data_api_roles(cursor)
    for name, arguments in functions:
        # The server produces a quoted, type-only function signature. Names are
        # quoted independently, and credentials never enter this DDL.
        target = sql.SQL("{}({})").format(sql.Identifier("public", name), sql.SQL(arguments))
        cursor.execute(sql.SQL("REVOKE ALL ON FUNCTION {} FROM PUBLIC").format(target))
        for role in denied:
            cursor.execute(sql.SQL("REVOKE ALL ON FUNCTION {} FROM {}").format(target, sql.Identifier(role)))
        cursor.execute(sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(target, sql.Identifier(runtime_role)))
