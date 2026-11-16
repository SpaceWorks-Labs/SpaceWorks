import pytest

from config.cloud_database import DatabaseConfigurationError, database_spec
from config.cloud_database.principal import database_principal


def test_shared_pooler_wire_login_does_not_become_the_sql_role_name():
    spec = database_spec("postgresql://spaceworks_app.projectref:secret@aws-0.pooler.supabase.com:5432/postgres?sslmode=require", mode="session", managed=True, environ={})
    assert database_principal(spec) == "spaceworks_app"
    assert spec.parameters["user"] == "spaceworks_app.projectref"


def test_direct_role_name_is_preserved():
    spec = database_spec("postgresql://spaceworks_app:secret@db.projectref.supabase.co:5432/postgres?sslmode=require", mode="direct", managed=True, environ={})
    assert database_principal(spec) == "spaceworks_app"


def test_shared_pooler_missing_project_suffix_refuses():
    spec = database_spec("postgresql://spaceworks_app:secret@aws-0.pooler.supabase.com:5432/postgres?sslmode=require", mode="session", managed=True, environ={})
    with pytest.raises(DatabaseConfigurationError):
        database_principal(spec)
