"""Final audit m21: GuestPass rows are accountability evidence, enforced by Postgres.

DELETE is refused outside the `app.allow_immutable_delete` purge scope (the same escape hatch the
other immutable tables use). UPDATE may not touch the frozen identity columns, and a pass that is no
longer live (expired / revoked / converted) never changes status again, so history cannot be rewritten.
The window, waiver triple, revoke fields and the SET_NULL actor links stay writable (event moves
re-window a live pass; user deletion nulls actor FKs).
"""
from django.db import migrations

SQL = """
CREATE FUNCTION makerspaces_guest_pass_guard() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF current_setting('app.allow_immutable_delete', true) = 'on' THEN
      RETURN OLD;
    END IF;
    RAISE EXCEPTION 'guest passes are accountability evidence and cannot be deleted';
  END IF;
  IF NEW.makerspace_id IS DISTINCT FROM OLD.makerspace_id
     OR NEW.holder_id IS DISTINCT FROM OLD.holder_id
     OR NEW.kind IS DISTINCT FROM OLD.kind
     OR NEW.product_id IS DISTINCT FROM OLD.product_id
     OR NEW.entitlements IS DISTINCT FROM OLD.entitlements
     OR NEW.operation_id IS DISTINCT FROM OLD.operation_id
     OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'guest pass identity and frozen entitlements are immutable';
  END IF;
  IF OLD.status IN ('expired', 'revoked', 'converted') AND NEW.status IS DISTINCT FROM OLD.status THEN
    RAISE EXCEPTION 'a closed guest pass cannot change status';
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER makerspaces_guest_pass_guard_trigger BEFORE UPDATE OR DELETE
  ON makerspaces_guestpass FOR EACH ROW EXECUTE FUNCTION makerspaces_guest_pass_guard();
"""
REVERSE_SQL = """
DROP TRIGGER IF EXISTS makerspaces_guest_pass_guard_trigger ON makerspaces_guestpass;
DROP FUNCTION IF EXISTS makerspaces_guest_pass_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0138_community_minors_volunteers")]
    operations = [migrations.RunSQL(SQL, REVERSE_SQL)]
