"""Typed ownership cannot be reassigned through direct SQL or portable row writes."""

from django.db import migrations

FORWARD = """
CREATE FUNCTION booking_website_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='bookings_bookingresourcepage' THEN
    IF TG_OP='UPDATE' AND NEW.space_id<>OLD.space_id THEN
      RAISE EXCEPTION 'Website owner is immutable' USING ERRCODE='23514';
    END IF;
  ELSE
    IF TG_OP='UPDATE' AND NEW.page_id<>OLD.page_id THEN
      RAISE EXCEPTION 'Website child owner is immutable' USING ERRCODE='23514';
    END IF;
    IF TG_TABLE_NAME='bookings_bookingresourcepagesection' THEN
      IF NEW.asset_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM bookings_bookingresourcepageasset
                       WHERE id=NEW.asset_id AND page_id=NEW.page_id) THEN
        RAISE EXCEPTION 'Asset must belong to the section page' USING ERRCODE='23514';
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END $$;
"""
TABLES = ("bookingresourcepage", "bookingresourcepageasset", "bookingresourcepagesection")


class Migration(migrations.Migration):
    dependencies = [("bookings", "0017_resource_website")]
    operations = [migrations.RunSQL(
        FORWARD + "\n".join(
            f"CREATE TRIGGER {name}_integrity BEFORE INSERT OR UPDATE ON bookings_{name} "
            "FOR EACH ROW EXECUTE FUNCTION booking_website_integrity();" for name in TABLES),
        "\n".join(f"DROP TRIGGER {name}_integrity ON bookings_{name};" for name in TABLES)
        + "\nDROP FUNCTION booking_website_integrity();",
    )]
