"""LOCAL ONLY (never committed): run the suite as the narrow runtime role, not the owner.

Enabled by ``--narrow-role`` (option and session fixture in tests/conftest.py). After pytest-django has created and migrated the
test database as the owner/superuser (post_migrate also ran rls_sync, so every policy exists),
this provisions ``spaceworks_app`` the way ``apps.backup.database_grants`` does for a bundled
install (DML on tables, sequences, functions; never an owner, superuser or BYPASSRLS), plus
TRUNCATE so transactional tests can flush, then reconnects every test as that role. With
TENANT_RLS_MODE=auto the role contract then decides ``enforce``, exactly like production.
"""

import pytest
from django.db import connections

ROLE = "spaceworks_app"
PASSWORD = "spaceworks-app-narrow-test"


def _provision(cursor):
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [ROLE])
    if cursor.fetchone() is None:
        cursor.execute(f'CREATE ROLE "{ROLE}" LOGIN PASSWORD %s', [PASSWORD])
    cursor.execute(f'ALTER ROLE "{ROLE}" LOGIN PASSWORD %s NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE '
                   "NOREPLICATION NOBYPASSRLS", [PASSWORD])
    cursor.execute("SELECT current_database()")
    database = cursor.fetchone()[0]
    cursor.execute(f'GRANT CONNECT ON DATABASE "{database}" TO "{ROLE}"')
    cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{ROLE}"')
    cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public TO "{ROLE}"')
    cursor.execute(f'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "{ROLE}"')
    cursor.execute(f'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO "{ROLE}"')


def narrow_session(request):
    """Generator used by tests/conftest.py's ``--narrow-role`` session fixture."""
    from apps.tenant_rls.role_contract import reset_cache

    request.getfixturevalue("django_db_setup")
    blocker = request.getfixturevalue("django_db_blocker")
    db = connections["default"]
    with blocker.unblock():
        with db.cursor() as cursor:
            _provision(cursor)
        owner = (db.settings_dict["USER"], db.settings_dict["PASSWORD"])
        db.close()
        db.settings_dict["USER"], db.settings_dict["PASSWORD"] = ROLE, PASSWORD
        reset_cache()
        with db.cursor() as cursor:
            cursor.execute("SELECT current_user")
            assert cursor.fetchone()[0] == ROLE
    yield
    with blocker.unblock():
        db.close()
        db.settings_dict["USER"], db.settings_dict["PASSWORD"] = owner
        reset_cache()
