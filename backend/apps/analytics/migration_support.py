"""Shared migration step for ALTERs of columns the curated analytics views read.

A view blocks ALTER TYPE on every column it selects. ``manage.py migrate`` drops the views
first (``db_sync.pre_migrate_drop``, sent as the ``pre_migrate`` signal) and ``analytics_sync``
rebuilds them afterwards, but a bare ``MigrationExecutor`` (tests, tooling) sends no signal, so
a money-column alter - forward or in reverse - must not depend on it. Dropping is idempotent
and the views are derived objects.

This is a custom operation, not ``RunPython``: RunPython renders the whole project state
(every model of every app) before it runs, which on late migrations costs minutes and
gigabytes per use. This one touches only the database.
"""
from django.db import migrations


class DropAnalyticsViews(migrations.operations.base.Operation):
    reversible = True
    reduces_to_sql = False
    atomic = True

    def state_forwards(self, app_label, state):
        pass

    def _drop(self, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        from apps.analytics import db_ddl

        with schema_editor.connection.cursor() as cursor:
            db_ddl.drop_view_schemas(cursor)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        self._drop(schema_editor)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        self._drop(schema_editor)

    def describe(self):
        return "Drop the derived analytics views (rebuilt by analytics_sync)"


def drop_views_operation():
    return DropAnalyticsViews()
