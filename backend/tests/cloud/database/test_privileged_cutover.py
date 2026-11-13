"""Real independent databases prove post-cutover DDL targets only the admitted B."""
from contextlib import contextmanager
from types import SimpleNamespace
import uuid

import psycopg2
from psycopg2 import sql
import pytest

from apps.backup.database_identity import query_live_database_identity
from apps.backup.host_marker import DatabaseIdentity, MarkerStage
from apps.backup.privileged_target import privileged_url, verify_target
from apps.tenant_migration.tenant_dump_database import _database_url
from config.cloud_database import django_database_spec

pytestmark = pytest.mark.django_db(transaction=True)


@contextmanager
def databases():
    parameters = django_database_spec().kwargs()
    owner = psycopg2.connect(**parameters)
    owner.autocommit = True
    created = []
    try:
        for _ in range(2):
            name = "cloud_target_" + uuid.uuid4().hex[:20]
            with owner.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            created.append(name)
            connection = psycopg2.connect(**{**parameters, "dbname": name})
            try:
                connection.autocommit = True
                with connection.cursor() as cursor:
                    cursor.execute("CREATE TABLE backup_deploymentdatabaseidentity (id integer PRIMARY KEY, database_uuid uuid, run_id uuid, artifact_sha256 text, capture_id uuid)")
                    cursor.execute("INSERT INTO backup_deploymentdatabaseidentity VALUES (1,%s,NULL,'',NULL)", [str(uuid.uuid4())])
            finally:
                connection.close()
        yield parameters, created
    finally:
        for name in created:
            with owner.cursor() as cursor:
                cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        owner.close()


def url(parameters, name):
    return _database_url({"ENGINE": "django.db.backends.postgresql", "NAME": name,
        "HOST": parameters["host"], "PORT": parameters.get("port", 5432),
        "USER": parameters["user"], "PASSWORD": parameters.get("password", ""),
        "OPTIONS": {k:v for k,v in parameters.items() if k in {"sslmode", "sslrootcert", "sslcert", "sslkey"}}})


def test_original_a_to_admitted_b_cutover_does_not_modify_a():
    with databases() as (parameters, (original_a, sibling_b)):
        runtime_url = url(parameters, sibling_b)
        maintenance_url = url(parameters, original_a)
        database = psycopg2.connect(privileged_url(maintenance_url, runtime_url))
        try:
            database.autocommit = True
            live = query_live_database_identity(database)
            marker = SimpleNamespace(stage=MarkerStage.BOUND,
                database=DatabaseIdentity(sibling_b, live.oid, live.server_identity()))
            expected = {"SPACEWORKS_PRIVILEGED_TARGET_REQUIRED": "1",
                        "SPACEWORKS_PRIVILEGED_TARGET_NAME": sibling_b,
                        "SPACEWORKS_PRIVILEGED_TARGET_OID": str(live.oid),
                        "SPACEWORKS_PRIVILEGED_TARGET_UUID": live.database_uuid}
            verify_target(database, marker, runtime_url, expected)
            with database.cursor() as cursor:
                cursor.execute("CREATE TABLE migration_effect (id integer PRIMARY KEY)")
            for changed in ({"SPACEWORKS_PRIVILEGED_TARGET_NAME": original_a},
                            {"SPACEWORKS_PRIVILEGED_TARGET_OID": str(live.oid + 1)},
                            {"SPACEWORKS_PRIVILEGED_TARGET_UUID": str(uuid.uuid4())}):
                with pytest.raises(ValueError):
                    verify_target(database, marker, runtime_url, {**expected, **changed})
        finally:
            database.close()
        database = psycopg2.connect(**{**parameters, "dbname": original_a})
        try:
            with database.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.migration_effect')")
                assert cursor.fetchone() == (None,)
        finally:
            database.close()
