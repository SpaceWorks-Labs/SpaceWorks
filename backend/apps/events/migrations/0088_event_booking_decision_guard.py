from django.db import migrations

SQL = """
CREATE FUNCTION events_booking_decision_owner_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM events_event e WHERE e.id = NEW.event_id AND e.makerspace_id = NEW.makerspace_id) THEN
        RAISE EXCEPTION 'event booking decision event is outside its maker';
    END IF;
    IF NEW.booking_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM bookings_booking b JOIN bookings_bookablespace s ON s.id = b.space_id
        WHERE b.id = NEW.booking_id AND s.makerspace_id = NEW.makerspace_id
    ) THEN
        RAISE EXCEPTION 'event booking decision booking is outside its maker';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER event_booking_decision_owner BEFORE INSERT
ON events_eventbookingdecision FOR EACH ROW EXECUTE FUNCTION events_booking_decision_owner_guard();
CREATE FUNCTION events_booking_decision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('app.booking_decision_purge_id', true) = OLD.id::text
       AND current_setting('app.booking_decision_purge_maker', true) = OLD.makerspace_id::text THEN
        IF TG_OP = 'DELETE' AND current_setting('app.booking_decision_purge_action', true) = 'delete' THEN
            RETURN OLD;
        END IF;
        IF TG_OP = 'UPDATE' AND current_setting('app.booking_decision_purge_action', true) = 'detach'
           AND OLD.booking_id IS NOT NULL AND NEW.booking_id IS NULL
           AND (to_jsonb(NEW) - 'booking_id') = (to_jsonb(OLD) - 'booking_id') THEN
            RETURN NEW;
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.creator_id IS NOT NULL AND NEW.creator_id IS NULL
       AND current_setting('app.booking_decision_creator_row', true) = OLD.id::text
       AND current_setting('app.booking_decision_creator_maker', true) = OLD.makerspace_id::text
       AND current_setting('app.booking_decision_creator_user', true) = OLD.creator_id::text
       AND NEW.intent = '{"version": 1, "unavailable": true}'::jsonb
       AND (to_jsonb(NEW) - ARRAY['creator_id', 'intent']) = (to_jsonb(OLD) - ARRAY['creator_id', 'intent']) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'event booking decision is immutable';
END;
$$;
CREATE TRIGGER event_booking_decision_immutable BEFORE UPDATE OR DELETE
ON events_eventbookingdecision FOR EACH ROW EXECUTE FUNCTION events_booking_decision_guard();
"""
REVERSE = """
DROP TRIGGER IF EXISTS event_booking_decision_owner ON events_eventbookingdecision;
DROP FUNCTION IF EXISTS events_booking_decision_owner_guard();
DROP TRIGGER IF EXISTS event_booking_decision_immutable ON events_eventbookingdecision;
DROP FUNCTION IF EXISTS events_booking_decision_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0087_event_booking_decision")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
