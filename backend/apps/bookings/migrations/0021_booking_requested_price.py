"""Lane L15 (#159): a booking awaiting approval keeps the price quoted when it was requested.

`pricing_snapshot` holds that frozen quote; approval charges exactly it. Insert-only, like
`Payment.pricing_snapshot`: the model refuses a change and this trigger backs it. Existing
rows get `{}` and fall back to the approval-day quote (audited).
"""

from django.db import migrations, models

GUARD_SQL = """
CREATE OR REPLACE FUNCTION bookings_booking_price_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.pricing_snapshot IS DISTINCT FROM OLD.pricing_snapshot THEN
    RAISE EXCEPTION 'a booking requested price is frozen';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER bookings_booking_price_guard BEFORE UPDATE ON bookings_booking
FOR EACH ROW EXECUTE FUNCTION bookings_booking_price_guard();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS bookings_booking_price_guard ON bookings_booking;
DROP FUNCTION IF EXISTS bookings_booking_price_guard();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0020_p2_bookings'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='pricing_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunSQL(GUARD_SQL, DROP_SQL),
    ]
