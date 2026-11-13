"""Real grants/negative rights; the owner transaction rolls back every global DDL."""

from unittest.mock import Mock
import uuid

import psycopg2
from psycopg2 import sql
import pytest

from apps.backup.database_grants import GrantTarget, provision_runtime_role
from apps.backup.managed.runtime_grants import apply_managed_grants
from apps.backup.managed.runtime_rights import prove_runtime_rights
from apps.backup.managed.function_grants import grant_application_functions
from apps.backup.database_grants import DatabaseGrantError
from config.cloud_database import django_database_spec


pytestmark = pytest.mark.django_db(transaction=True)


def test_runtime_role_can_use_app_rows_but_cannot_create_or_own_objects():
    database = psycopg2.connect(**django_database_spec().kwargs())
    role = "cloud_runtime_" + uuid.uuid4().hex[:12]
    table = "cloud_runtime_table_" + uuid.uuid4().hex[:12]
    try:
        with database.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            name = cursor.fetchone()[0]
            cursor.execute(sql.SQL("CREATE TABLE public.{} (id bigserial PRIMARY KEY, value text NOT NULL)").format(sql.Identifier(table)))
            provision_runtime_role(cursor, GrantTarget(name, role), "disposable-test-password")
            apply_managed_grants(cursor, role, {table})
            cursor.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            prove_runtime_rights(cursor, {table})
            cursor.execute(sql.SQL("INSERT INTO public.{} (value) VALUES ('allowed') RETURNING id").format(sql.Identifier(table)))
            assert cursor.fetchone()[0] >= 1
            cursor.execute("SELECT has_schema_privilege(current_user,'public','CREATE'), has_database_privilege(current_user,current_database(),'CREATE')")
            assert cursor.fetchone() == (False, False)
            cursor.execute("SELECT rolinherit, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user")
            assert cursor.fetchone() == (False,) * 6
    finally:
        database.rollback()
        database.close()


def test_unclassified_app_function_is_refused_before_any_grant():
    cursor = Mock()
    cursor.fetchall.return_value = [("unknown_application_function", "")]
    with pytest.raises(DatabaseGrantError, match="unclassified"):
        grant_application_functions(cursor, "runtime")
    assert cursor.execute.call_count == 1
