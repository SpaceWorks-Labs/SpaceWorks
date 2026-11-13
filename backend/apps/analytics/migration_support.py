"""Shared migration step for ALTERs of columns the curated analytics views read.

A view blocks ALTER TYPE on every column it selects. ``manage.py migrate`` drops the views
first (``db_sync.pre_migrate_drop``, sent as the ``pre_migrate`` signal) and ``analytics_sync``
rebuilds them afterwards, but a bare ``MigrationExecutor`` (tests, tooling) sends no signal, so
a money-column alter - forward or in reverse - must not depend on it. Dropping is idempotent
and the views are derived objects.
"""
from django.db import migrations


def drop_analytics_views(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    from apps.analytics import db_ddl

    with schema_editor.connection.cursor() as cursor:
        db_ddl.drop_view_schemas(cursor)


def drop_views_operation():
    return migrations.RunPython(drop_analytics_views, drop_analytics_views)
