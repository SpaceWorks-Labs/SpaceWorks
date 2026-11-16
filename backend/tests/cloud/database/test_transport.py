import os
from pathlib import Path

import pytest

from config.cloud_database import DatabaseConfigurationError, database_spec
from config.cloud_database.subprocess import postgres_environment


@pytest.mark.parametrize("url,mode", [
    ("postgresql://app:secret@aws-0.pooler.supabase.com:6543/db?sslmode=require", "session"),
    ("postgresql://app:secret@ep-a-pooler.us.neon.tech/db?sslmode=require", "direct"),
    ("postgresql://app:secret@db.example/db?sslmode=require", "transaction"),
    ("postgresql://app:secret@aws-0.pooler.supabase.com:5432/db?sslmode=require", "direct"),
])
def test_known_transaction_endpoints_refuse_before_connect(url, mode):
    with pytest.raises(DatabaseConfigurationError):
        database_spec(url, mode=mode, managed=True, environ={})


def test_session_pooler_tls_and_escaping_are_preserved():
    spec = database_spec("postgresql://app:p%40ss%3Aword@aws-0.pooler.supabase.com:5432/db?sslmode=verify-full&sslrootcert=%2Fcerts%2Froot.pem", mode="session", managed=True, environ={})
    assert spec.parameters["password"] == "p@ss:word"
    assert spec.parameters["sslrootcert"] == "/certs/root.pem"
    assert "p@ss" not in repr(spec)


@pytest.mark.parametrize("query", ["", "?sslmode=disable", "?sslmode=prefer"])
def test_remote_managed_database_requires_tls(query):
    with pytest.raises(DatabaseConfigurationError):
        database_spec("postgresql://app:secret@db.example/db" + query, mode="direct", managed=True, environ={})


def test_unknown_provider_requires_an_explicit_transport_declaration():
    with pytest.raises(DatabaseConfigurationError):
        database_spec("postgresql://app:secret@db.example/db?sslmode=require", managed=True, environ={})


def test_pgpass_is_private_scrubs_environment_and_is_removed_on_failure():
    spec = database_spec("postgresql://app:p%3Aa%5Css@db.example/db?sslmode=verify-full&sslrootcert=%2Fca.pem", mode="direct", managed=True, environ={})
    passfile = None
    with pytest.raises(RuntimeError):
        with postgres_environment(spec, environ={"PATH": "bin", "PGPASSWORD": "inherited", "PGSERVICE": "bad", "PGOPTIONS": "bad"}) as (argv, environment):
            passfile = Path(environment["PGPASSFILE"])
            assert passfile.exists()
            if os.name != "nt":
                assert passfile.stat().st_mode & 0o777 == 0o600
            assert "PGPASSWORD" not in environment and "PGSERVICE" not in environment
            assert environment["PGSSLMODE"] == "verify-full"
            assert environment["PGSSLROOTCERT"] == "/ca.pem"
            assert not any("p:a" in value for value in argv)
            assert r"p\:a\\ss" in passfile.read_text()
            raise RuntimeError("simulated tool failure")
    assert passfile is not None and not passfile.exists()


def test_bad_url_diagnostic_cannot_expose_password():
    with pytest.raises(DatabaseConfigurationError) as error:
        database_spec("postgresql://owner:very-secret@host:bad-port/db", mode="direct", managed=True, environ={})
    assert "very-secret" not in str(error.value)


@pytest.mark.parametrize("name", ["PGSERVICE", "PGPASSWORD", "PGOPTIONS", "PGHOSTADDR"])
def test_managed_driver_rejects_inherited_redirects(name):
    with pytest.raises(DatabaseConfigurationError):
        database_spec("postgresql://app:secret@db.example/db?sslmode=require", mode="direct", managed=True, environ={name: "override"})
