"""The PostgreSQL client tools under RLS (one hook in ``backup.postgres_client.run_client``).

``pg_dump`` turns ``row_security`` off and then refuses every table a policy would apply
to, so each data dump is sent ``--enable-row-security``. A client-tool session is never
bound (no ``app.*`` settings), so the policies admit every row and the dump is complete.
No ``PGOPTIONS`` is sent: managed transports refuse inherited startup options, and
transaction poolers reject them. Schema-only dumps read no rows and are left untouched.
"""


def client_arguments(tool, arguments):
    arguments = list(arguments)
    if tool == "pg_dump" and "--schema-only" not in arguments and "--enable-row-security" not in arguments:
        arguments.insert(0, "--enable-row-security")
    return arguments


def is_scratch_database(cursor):
    """Throwaway Lane D projection databases are never served and are not policed.

    Their data-only source restore COPYs into migrated tables as the owner, which FORCE
    row-level security would refuse; the target database applies its own policies.
    """
    cursor.execute(
        r"SELECT current_database() LIKE 'spaceworks\_dump\_%%' "
        "OR to_regclass('public.spaceworks_scratch_identity') IS NOT NULL")
    return bool(cursor.fetchone()[0])
