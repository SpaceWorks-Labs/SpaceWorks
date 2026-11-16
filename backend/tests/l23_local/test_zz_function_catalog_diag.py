"""Local diagnostic (never committed): name every application-owned SQL function the managed catalog lacks."""
import pytest
from django.db import connection

from apps.backup.managed.function_catalog import APPLICATION_FUNCTIONS


@pytest.mark.django_db
def test_every_application_function_is_classified():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='public' AND p.proowner=(SELECT oid FROM pg_roles WHERE rolname=current_user) "
            "AND p.prokind='f' AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass "
            "AND d.objid=p.oid AND d.deptype='e')")
        names = sorted({row[0] for row in cursor.fetchall()})
    assert [name for name in names if name not in APPLICATION_FUNCTIONS] == []
