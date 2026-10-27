"""P1b (owner decision #111 Q8): drop Lane E restore reservations and slice state.

With the superadmin always on there are no sovereign slices, so nothing ever seeds
an opaque restore component, installs a reservation or runs a delayed merge. Every
`backup_b1_*` function goes first (CASCADE removes its triggers, including the
makerspace materialization guard and any installed reservation guard), then
`accounts_guard_context` loses its B1 staff-shell branch, then the four tables in
foreign-key order. Reverse recreates the tables and replays the original SQL.
"""

from importlib import import_module

from django.db import migrations


DROP_B1_FUNCTIONS = r"""
DO $$
DECLARE
  item record;
BEGIN
  FOR item IN
    SELECT p.oid::regprocedure AS signature
      FROM pg_catalog.pg_proc p
      JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public' AND p.proname LIKE 'backup\_b1\_%'
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', item.signature);
  END LOOP;
END;
$$;
"""


def _constant(app, name, constant):
    return getattr(import_module(f"apps.{app}.migrations.{name}"), constant)


def _forward_sql():
    accounts_without_b1 = _constant(
        "accounts", "0035_as_p4_guarded_shell_restore", "REVERSE"
    )
    return DROP_B1_FUNCTIONS + "\n" + accounts_without_b1


def _reverse_sql():
    return "\n".join((
        _constant("backup", "0017_b1_restore_state_guards", "STATE_GUARDS"),
        _constant("backup", "0018_b1_reservation_enforcement", "ENFORCEMENT"),
        _constant("backup", "0019_b1_delayed_slice_merge", "GUARDS"),
        _constant("accounts", "0035_as_p4_guarded_shell_restore", "SQL"),
    ))


class Migration(migrations.Migration):
    dependencies = [
        ("backup", "0031_remove_archive_decision_snapshot"),
        ("accounts", "0035_as_p4_guarded_shell_restore"),
    ]

    operations = [
        migrations.RunSQL(_forward_sql(), _reverse_sql()),
        migrations.DeleteModel(name="B1FenceContinuity"),
        migrations.DeleteModel(name="B1ReservationEntry"),
        migrations.DeleteModel(name="B1RestoreComponentState"),
        migrations.DeleteModel(name="B1RestoreOperationState"),
    ]
