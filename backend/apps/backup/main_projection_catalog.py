"""Physical-table guard for the readable-main projection registry."""

from django.db import connections
from apps.backup.build_errors import BackupBuildError

def assert_catalog_matches(using, rules):
    from .main_projection_registry import DJANGO_RUNTIME_TABLES
    connection = connections[using]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname
              FROM pg_catalog.pg_class c
              JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
             ORDER BY c.relname
            """
        )
        actual = {row[0] for row in cursor.fetchall()}
    expected = {rule.model._meta.db_table for rule in rules} | DJANGO_RUNTIME_TABLES
    if actual != expected:
        missing = sorted(actual - expected)
        stale = sorted(expected - actual)
        raise BackupBuildError(
            "Readable-main physical-table registry drift: "
            f"unclassified={missing}, absent={stale}."
        )
