"""Cross-row editorial ownership must also hold for direct SQL/import writers."""

from django.db import migrations

FORWARD = """
-- Match ZoneInfo fold=0: the earlier real instant during an overlap, and the
-- pre-transition offset for a nonexistent wall time (recurrence skips that date).
CREATE FUNCTION event_website_wall_start(wall timestamp, zone_name text)
RETURNS timestamptz LANGUAGE sql STABLE STRICT AS $wall$
  WITH base AS (SELECT wall AT TIME ZONE zone_name AS guess),
  offsets AS (
    SELECT DISTINCT (ref AT TIME ZONE zone_name) - (ref AT TIME ZONE 'UTC') AS off
    FROM base, LATERAL (VALUES (guess - interval '48 hours'), (guess),
                              (guess + interval '48 hours')) points(ref)
  ), candidates AS (SELECT (wall AT TIME ZONE 'UTC') - off AS instant FROM offsets)
  SELECT coalesce(min(instant) FILTER (WHERE instant AT TIME ZONE zone_name = wall),
                  max(instant) FILTER (WHERE instant AT TIME ZONE zone_name > wall))
  FROM candidates
$wall$;
CREATE FUNCTION event_website_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p events_eventpage; linked_page bigint; linked_kind text; lo timestamptz; hi timestamptz;
BEGIN
  IF TG_TABLE_NAME = 'events_eventpage' THEN
    IF NEW.event_id IS NOT NULL THEN
      SELECT makerspace_id INTO linked_page FROM events_event WHERE id=NEW.event_id;
    ELSE
      SELECT makerspace_id INTO linked_page FROM events_eventseries WHERE id=NEW.series_id;
    END IF;
    IF linked_page IS DISTINCT FROM NEW.makerspace_id THEN
      RAISE EXCEPTION 'Website owner must share its tenant' USING ERRCODE='23514';
    END IF;
    IF TG_OP='UPDATE' AND (NEW.event_id IS DISTINCT FROM OLD.event_id OR
       NEW.series_id IS DISTINCT FROM OLD.series_id OR NEW.makerspace_id<>OLD.makerspace_id) THEN
      RAISE EXCEPTION 'Website owner is immutable' USING ERRCODE='23514';
    END IF;
  ELSIF TG_TABLE_NAME='events_eventsessionspeaker' THEN
    SELECT page_id INTO linked_page FROM events_eventsession WHERE id=NEW.session_id;
    IF NOT EXISTS (SELECT 1 FROM events_eventpagesection WHERE id=NEW.speaker_id
                   AND page_id=linked_page AND kind='speaker') THEN
      RAISE EXCEPTION 'Speaker must belong to the session page' USING ERRCODE='23514';
    END IF;
  ELSE
    IF TG_OP='UPDATE' AND NEW.page_id<>OLD.page_id THEN
      RAISE EXCEPTION 'Website child page is immutable' USING ERRCODE='23514';
    END IF;
    IF TG_TABLE_NAME='events_eventpagesection' THEN
      IF NEW.asset_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventpageasset
         WHERE id=NEW.asset_id AND page_id=NEW.page_id) THEN
        RAISE EXCEPTION 'Asset must belong to the section page' USING ERRCODE='23514';
      END IF;
      IF TG_OP='UPDATE' AND NEW.kind<>OLD.kind AND (
        EXISTS (SELECT 1 FROM events_eventsession WHERE track_id=NEW.id OR room_id=NEW.id) OR
        EXISTS (SELECT 1 FROM events_eventsessionspeaker WHERE speaker_id=NEW.id)) THEN
        RAISE EXCEPTION 'Referenced section kind is immutable' USING ERRCODE='23514';
      END IF;
    ELSIF TG_TABLE_NAME='events_eventsession' THEN
      IF NEW.track_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventpagesection
         WHERE id=NEW.track_id AND page_id=NEW.page_id AND kind='track') THEN
        RAISE EXCEPTION 'Track must belong to the session page' USING ERRCODE='23514';
      END IF;
      IF NEW.room_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventpagesection
         WHERE id=NEW.room_id AND page_id=NEW.page_id AND kind='room') THEN
        RAISE EXCEPTION 'Room must belong to the session page' USING ERRCODE='23514';
      END IF;
      SELECT * INTO p FROM events_eventpage WHERE id=NEW.page_id;
      IF p.event_id IS NOT NULL THEN
        SELECT starts_at, ends_at INTO lo, hi FROM events_event WHERE id=p.event_id FOR NO KEY UPDATE;
      ELSE
        SELECT event_website_wall_start(dtstart_local_date + dtstart_local_time, recurrence_timezone),
          (event_website_wall_start(dtstart_local_date + dtstart_local_time, recurrence_timezone))
          + duration_minutes * interval '1 minute' INTO lo, hi FROM events_eventseries WHERE id=p.series_id FOR NO KEY UPDATE;
      END IF;
      IF p.series_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM events_event e WHERE e.series_id=p.series_id
        AND NOT EXISTS (SELECT 1 FROM events_eventpage own WHERE own.event_id=e.id)
        AND NEW.ends_at-lo > e.ends_at-e.starts_at
      ) THEN
        RAISE EXCEPTION 'Session exceeds an inheriting occurrence window' USING ERRCODE='23514';
      END IF;
      IF NEW.starts_at<lo OR NEW.ends_at>hi THEN
        RAISE EXCEPTION 'Session must lie within its owner window' USING ERRCODE='23514';
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END $$;
"""

TABLES = ("eventpage", "eventpageasset", "eventpagesection", "eventsession", "eventsessionspeaker")


class Migration(migrations.Migration):
    dependencies = [("events", "0031_event_website")]
    operations = [migrations.RunSQL(
        FORWARD + "\n".join(
            f"CREATE TRIGGER event_website_integrity BEFORE INSERT OR UPDATE ON events_{name} "
            "FOR EACH ROW EXECUTE FUNCTION event_website_integrity();" for name in TABLES),
        "\n".join(f"DROP TRIGGER IF EXISTS event_website_integrity ON events_{name};" for name in TABLES)
        + "\nDROP FUNCTION event_website_integrity(); DROP FUNCTION event_website_wall_start(timestamp, text);",
    )]
