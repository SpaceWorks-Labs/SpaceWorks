"""Database-only money ALTER brackets: preserve only the affected dependency closure.

Read frozen operations and ModelState without rendering the historical app registry.
Schemas, default privileges and unaffected relations retain their identities.
"""
from importlib import import_module

from django.db import migrations

from .migration_views import restore as _restore, suspend as _suspend

MONEY_MIGRATIONS = {
    "bookings": "0030", "events": "0092", "inventory": "0022", "machines": "0037",
    "maintenance": "0012", "makerspaces": "0143", "payments": "0049",
    "procurement": "0011", "shop": "0004",
}


def altered_columns(app_label, state):
    """Find the actual ALTER columns without rendering state.apps."""
    number = MONEY_MIGRATIONS[app_label]
    module = import_module(f"apps.{app_label}.migrations.{number}_money_three_decimals")
    result = []
    for operation in module.Migration.operations:
        if isinstance(operation, migrations.AlterField):
            model = state.models[(app_label, operation.model_name)]
            table = model.options.get("db_table", f"{app_label}_{operation.model_name}")
            result.append((table, operation.field.db_column or operation.name))
    return result


class DropAnalyticsViews(migrations.operations.base.Operation):
    reversible = True
    reduces_to_sql = False
    atomic = True

    def __init__(self, *, restore=False):
        self.restore = restore

    def state_forwards(self, app_label, state):
        pass

    def _apply(self, app_label, schema_editor, state, *, restore):
        db = schema_editor.connection
        if db.vendor != "postgresql":
            return
        snapshots = getattr(db, "_analytics_migration_views", None)
        if snapshots is None:
            snapshots = db._analytics_migration_views = {}
        if restore:
            _restore(db, snapshots[app_label])
            del snapshots[app_label]
        else:
            snapshots[app_label] = _suspend(db, altered_columns(app_label, state))

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        self._apply(app_label, schema_editor, from_state, restore=self.restore)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        self._apply(app_label, schema_editor, from_state, restore=not self.restore)

    def describe(self):
        return "Restore dependent views and ACLs" if self.restore else "Suspend dependent views for ALTER"


def drop_views_operation():
    return DropAnalyticsViews()


def restore_views_operation():
    return DropAnalyticsViews(restore=True)
