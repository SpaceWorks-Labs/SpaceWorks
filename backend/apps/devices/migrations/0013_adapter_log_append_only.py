"""Adapter event, access-decision and usage logs are append-only at the DATABASE (SECURITY-REVIEW L-A4).

Until now only ``Model.save`` refused an update, so ``QuerySet.update()`` or raw SQL could rewrite the evidence.
The guard mirrors ``devices_event_append_only`` (0001) with two narrow allowances the schema itself needs:

* an ``ON DELETE SET NULL`` reference (the binding of an unbound target, the member of a deleted account) may turn
  NULL, and nothing else in the row may change in the same statement;
* an account merge (``app.account_unification_run_id`` set, ``accounts.account_merge``) may move ``member_id`` to the
  surviving account, as the merge registry records for ``AdapterAccessLog.member``.

DELETE is allowed only inside an authorized purge (``app.allow_immutable_delete``), exactly like every other
immutable table; self-host purges run as the replica role, which skips triggers.
"""
from django.db import migrations

GUARD_SQL = """CREATE OR REPLACE FUNCTION devices_adapter_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  old_row jsonb := to_jsonb(OLD);
  new_row jsonb := to_jsonb(NEW);
  col text;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF current_setting('app.allow_immutable_delete', true) = 'on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'adapter logs are append-only';
  END IF;
  IF TG_NARGS > 0 THEN
    FOREACH col IN ARRAY TG_ARGV LOOP
      IF (new_row -> col) IS DISTINCT FROM (old_row -> col)
         AND jsonb_typeof(new_row -> col) <> 'null'
         AND NOT (col = 'member_id'
                  AND coalesce(current_setting('app.account_unification_run_id', true), '') <> '') THEN
        RAISE EXCEPTION 'adapter logs are append-only';
      END IF;
      old_row := old_row - col;
      new_row := new_row - col;
    END LOOP;
  END IF;
  IF new_row IS DISTINCT FROM old_row THEN
    RAISE EXCEPTION 'adapter logs are append-only';
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS devices_adapterevent_append_only ON devices_adapterevent;
CREATE TRIGGER devices_adapterevent_append_only
BEFORE UPDATE OR DELETE ON devices_adapterevent
FOR EACH ROW EXECUTE FUNCTION devices_adapter_log_append_only('binding_id');
DROP TRIGGER IF EXISTS devices_adapteraccesslog_append_only ON devices_adapteraccesslog;
CREATE TRIGGER devices_adapteraccesslog_append_only
BEFORE UPDATE OR DELETE ON devices_adapteraccesslog
FOR EACH ROW EXECUTE FUNCTION devices_adapter_log_append_only('binding_id', 'member_id');
DROP TRIGGER IF EXISTS devices_adapterusagelog_append_only ON devices_adapterusagelog;
CREATE TRIGGER devices_adapterusagelog_append_only
BEFORE UPDATE OR DELETE ON devices_adapterusagelog
FOR EACH ROW EXECUTE FUNCTION devices_adapter_log_append_only('binding_id');"""

DROP_GUARD_SQL = """DROP TRIGGER IF EXISTS devices_adapterevent_append_only ON devices_adapterevent;
DROP TRIGGER IF EXISTS devices_adapteraccesslog_append_only ON devices_adapteraccesslog;
DROP TRIGGER IF EXISTS devices_adapterusagelog_append_only ON devices_adapterusagelog;
DROP FUNCTION IF EXISTS devices_adapter_log_append_only();"""


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0012_shelf_check"),
    ]

    operations = [
        migrations.RunSQL(GUARD_SQL, DROP_GUARD_SQL),
    ]
