import pytest
from django.db import connection

from apps.tenant_rls.role_contract import effective_mode

pytestmark = pytest.mark.django_db


def test_suite_runs_as_the_narrow_role_with_rls_enforced():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        assert cursor.fetchone() == ("spaceworks_app", False, False)
        cursor.execute("SELECT count(*) FROM pg_policies WHERE policyname = 'spaceworks_rls_tenant'")
        assert cursor.fetchone()[0] > 100
    assert effective_mode(connection) == "enforce"
