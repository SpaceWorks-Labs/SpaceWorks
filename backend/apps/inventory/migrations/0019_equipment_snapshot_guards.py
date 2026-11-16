from django.db import migrations

SQL = """
CREATE FUNCTION inventory_equipment_snapshot_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE owner_id bigint;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'equipment snapshot is immutable';
    END IF;
    IF TG_TABLE_NAME = 'inventory_equipmentkitversion' THEN
        SELECT makerspace_id INTO owner_id
          FROM inventory_equipmentkittemplate WHERE id = OLD.template_id;
    ELSE
        owner_id := OLD.makerspace_id;
    END IF;
    IF TG_OP = 'DELETE' AND owner_id IS NOT NULL
       AND current_setting('app.equipment_purge_model', true) = TG_TABLE_NAME
       AND current_setting('app.equipment_purge_id', true) = OLD.id::text
       AND current_setting('app.equipment_purge_makerspace', true) = owner_id::text
    THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'equipment snapshot delete is not authorized';
END;
$$;
CREATE TRIGGER equipment_receipt_immutable BEFORE UPDATE OR DELETE
ON inventory_equipmentproposalreceipt FOR EACH ROW EXECUTE FUNCTION inventory_equipment_snapshot_guard();
CREATE TRIGGER equipment_plan_immutable BEFORE UPDATE OR DELETE
ON inventory_equipmentconsumableplan FOR EACH ROW EXECUTE FUNCTION inventory_equipment_snapshot_guard();
CREATE TRIGGER equipment_allocation_immutable BEFORE UPDATE OR DELETE
ON inventory_equipmentkitallocation FOR EACH ROW EXECUTE FUNCTION inventory_equipment_snapshot_guard();
CREATE TRIGGER equipment_version_immutable BEFORE UPDATE OR DELETE
ON inventory_equipmentkitversion FOR EACH ROW EXECUTE FUNCTION inventory_equipment_snapshot_guard();
"""

REVERSE = """
DROP TRIGGER IF EXISTS equipment_receipt_immutable ON inventory_equipmentproposalreceipt;
DROP TRIGGER IF EXISTS equipment_plan_immutable ON inventory_equipmentconsumableplan;
DROP TRIGGER IF EXISTS equipment_allocation_immutable ON inventory_equipmentkitallocation;
DROP TRIGGER IF EXISTS equipment_version_immutable ON inventory_equipmentkitversion;
DROP FUNCTION IF EXISTS inventory_equipment_snapshot_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("inventory", "0018_equipment_proposals")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
