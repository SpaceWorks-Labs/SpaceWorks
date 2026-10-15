from django.db import migrations

SQL = """
CREATE FUNCTION event_website_owner_window() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE lo timestamptz; hi timestamptz;
BEGIN
  IF TG_TABLE_NAME='events_event' THEN
    IF EXISTS (SELECT 1 FROM events_eventpage p JOIN events_eventsession s ON s.page_id=p.id
       WHERE p.event_id=NEW.id AND (s.starts_at<NEW.starts_at OR s.ends_at>NEW.ends_at)) THEN
      RAISE EXCEPTION 'Event window excludes its website sessions' USING ERRCODE='23514';
    END IF;
    IF NEW.series_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventpage WHERE event_id=NEW.id) THEN
      SELECT event_website_wall_start(dtstart_local_date+dtstart_local_time, recurrence_timezone) INTO lo
        FROM events_eventseries WHERE id=NEW.series_id FOR SHARE;
      IF EXISTS (SELECT 1 FROM events_eventpage p JOIN events_eventsession s ON s.page_id=p.id
         WHERE p.series_id=NEW.series_id AND s.ends_at-lo>NEW.ends_at-NEW.starts_at) THEN
        RAISE EXCEPTION 'Occurrence window excludes its inherited sessions' USING ERRCODE='23514';
      END IF;
    END IF;
  ELSE
    lo := event_website_wall_start(NEW.dtstart_local_date+NEW.dtstart_local_time, NEW.recurrence_timezone);
    hi := lo + NEW.duration_minutes * interval '1 minute';
    IF EXISTS (SELECT 1 FROM events_eventpage p JOIN events_eventsession s ON s.page_id=p.id
       WHERE p.series_id=NEW.id AND (s.starts_at<lo OR s.ends_at>hi)) THEN
      RAISE EXCEPTION 'Series window excludes its website sessions' USING ERRCODE='23514';
    END IF;
    IF EXISTS (SELECT 1 FROM events_eventpage p JOIN events_eventsession s ON s.page_id=p.id
       JOIN events_event e ON e.series_id=p.series_id
       WHERE p.series_id=NEW.id
       AND NOT EXISTS (SELECT 1 FROM events_eventpage own WHERE own.event_id=e.id)
       AND s.ends_at-lo>e.ends_at-e.starts_at) THEN
      RAISE EXCEPTION 'Series window excludes inherited website sessions' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER event_website_owner_window BEFORE INSERT OR UPDATE OF starts_at,ends_at,series_id
  ON events_event FOR EACH ROW EXECUTE FUNCTION event_website_owner_window();
CREATE TRIGGER event_website_owner_window BEFORE UPDATE OF dtstart_local_date,dtstart_local_time,recurrence_timezone,duration_minutes
  ON events_eventseries FOR EACH ROW EXECUTE FUNCTION event_website_owner_window();
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0031_website_constraints")]
    operations = [migrations.RunSQL(SQL, """
      DROP TRIGGER IF EXISTS event_website_owner_window ON events_event;
      DROP TRIGGER IF EXISTS event_website_owner_window ON events_eventseries;
      DROP FUNCTION event_website_owner_window();
    """)]
