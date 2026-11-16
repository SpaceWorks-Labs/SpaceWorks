"""Lane L22 database guards (the models refuse the same writes), and shop charge tracking on.

* `ShopOrder.pricing_snapshot` and `total` are frozen once the order is placed.
* `ShopStockMovement` and `ShopOrderReturn` are append-only: only the SET NULL of a purged
  order on a movement may touch a row; a cascade from a purged space still deletes them.
* A closed `ShopCashSession` is frozen.
* `charges.shop` (standalone, default on) is added to every existing space, so turning the
  shop on later never sells without recording the sale (#94). The module itself stays off.
"""

from django.db import migrations

GUARD_SQL = """
CREATE OR REPLACE FUNCTION shop_order_l22_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.pricing_snapshot IS DISTINCT FROM OLD.pricing_snapshot OR NEW.total IS DISTINCT FROM OLD.total THEN
    RAISE EXCEPTION 'a shop order quote is frozen once placed';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER shop_order_l22_guard BEFORE UPDATE ON shop_shoporder
FOR EACH ROW EXECUTE FUNCTION shop_order_l22_guard();

CREATE OR REPLACE FUNCTION shop_stockmovement_l22_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.variant_id IS DISTINCT FROM OLD.variant_id OR NEW.kind IS DISTINCT FROM OLD.kind
     OR NEW.quantity IS DISTINCT FROM OLD.quantity OR NEW.balance_after IS DISTINCT FROM OLD.balance_after
     OR NEW.reason IS DISTINCT FROM OLD.reason OR NEW.actor_id IS DISTINCT FROM OLD.actor_id
     OR NEW.created_at IS DISTINCT FROM OLD.created_at OR NEW.makerspace_id IS DISTINCT FROM OLD.makerspace_id
     OR (NEW.order_id IS NOT NULL AND NEW.order_id IS DISTINCT FROM OLD.order_id) THEN
    RAISE EXCEPTION 'shop stock movements are append-only';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER shop_stockmovement_l22_guard BEFORE UPDATE ON shop_shopstockmovement
FOR EACH ROW EXECUTE FUNCTION shop_stockmovement_l22_guard();

CREATE OR REPLACE FUNCTION shop_orderreturn_l22_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'shop returns are append-only';
END; $$;
CREATE TRIGGER shop_orderreturn_l22_guard BEFORE UPDATE ON shop_shoporderreturn
FOR EACH ROW EXECUTE FUNCTION shop_orderreturn_l22_guard();

CREATE OR REPLACE FUNCTION shop_cashsession_l22_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'closed' OR NEW.opening_float IS DISTINCT FROM OLD.opening_float THEN
    RAISE EXCEPTION 'a closed cash session is frozen';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER shop_cashsession_l22_guard BEFORE UPDATE ON shop_shopcashsession
FOR EACH ROW EXECUTE FUNCTION shop_cashsession_l22_guard();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS shop_cashsession_l22_guard ON shop_shopcashsession;
DROP FUNCTION IF EXISTS shop_cashsession_l22_guard();
DROP TRIGGER IF EXISTS shop_orderreturn_l22_guard ON shop_shoporderreturn;
DROP FUNCTION IF EXISTS shop_orderreturn_l22_guard();
DROP TRIGGER IF EXISTS shop_stockmovement_l22_guard ON shop_shopstockmovement;
DROP FUNCTION IF EXISTS shop_stockmovement_l22_guard();
DROP TRIGGER IF EXISTS shop_order_l22_guard ON shop_shoporder;
DROP FUNCTION IF EXISTS shop_order_l22_guard();
"""


def charges_on(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for space in Makerspace.objects.using(schema_editor.connection.alias).only("pk", "enabled_features").iterator():
        features = list(space.enabled_features or [])
        if "charges.shop" not in features:
            space.enabled_features = sorted({*features, "charges.shop"})
            space.save(update_fields=["enabled_features"])


class Migration(migrations.Migration):
    dependencies = [("shop", "0001_initial")]

    operations = [
        migrations.RunSQL(GUARD_SQL, DROP_SQL),
        migrations.RunPython(charges_on, migrations.RunPython.noop),
    ]
