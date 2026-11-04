"""Lane L6 database guards (the models refuse the same writes).

* `EventOrder.pricing_snapshot` and `total` are frozen once the order is placed: the
  price a buyer was shown is the price on the order, and L24 reads it back.
* `EventOrderDue` money is append-only: amount, order, kind, refund case and author never
  change. Only the SET NULL of a purged seat or event may touch a row; a cascade from a
  purged order or event still deletes it with its order.
"""

from django.db import migrations

GUARD_SQL = """
CREATE OR REPLACE FUNCTION events_order_l6_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.pricing_snapshot IS DISTINCT FROM OLD.pricing_snapshot OR NEW.total IS DISTINCT FROM OLD.total THEN
    RAISE EXCEPTION 'an order quote is frozen once placed';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER events_order_l6_guard BEFORE UPDATE ON events_eventorder
FOR EACH ROW EXECUTE FUNCTION events_order_l6_guard();

CREATE OR REPLACE FUNCTION events_orderdue_l6_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.amount IS DISTINCT FROM OLD.amount OR NEW.order_id IS DISTINCT FROM OLD.order_id
     OR NEW.kind IS DISTINCT FROM OLD.kind OR NEW.refund_case_id IS DISTINCT FROM OLD.refund_case_id
     OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id OR NEW.created_at IS DISTINCT FROM OLD.created_at
     OR (NEW.seat_id IS NOT NULL AND NEW.seat_id IS DISTINCT FROM OLD.seat_id)
     OR (NEW.event_id IS NOT NULL AND NEW.event_id IS DISTINCT FROM OLD.event_id) THEN
    RAISE EXCEPTION 'order dues are append-only';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER events_orderdue_l6_guard BEFORE UPDATE ON events_eventorderdue
FOR EACH ROW EXECUTE FUNCTION events_orderdue_l6_guard();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS events_orderdue_l6_guard ON events_eventorderdue;
DROP FUNCTION IF EXISTS events_orderdue_l6_guard();
DROP TRIGGER IF EXISTS events_order_l6_guard ON events_eventorder;
DROP FUNCTION IF EXISTS events_order_l6_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0064_l6_ticketing")]

    operations = [migrations.RunSQL(GUARD_SQL, DROP_SQL)]
