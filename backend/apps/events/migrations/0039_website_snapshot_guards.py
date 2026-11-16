"""Final-state pointer/identity/reference/window backstops for raw writers too."""

from django.db import migrations, models

SQL = """
CREATE FUNCTION event_asset_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Website image metadata is immutable' USING ERRCODE='23514';
END $$;
CREATE TRIGGER event_asset_immutable BEFORE UPDATE ON events_eventpageasset
FOR EACH ROW EXECUTE FUNCTION event_asset_immutable();
CREATE FUNCTION event_snapshot_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE alive boolean;
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete', true)='on' THEN RETURN OLD; END IF;
  IF TG_TABLE_NAME='events_eventpagerevision' THEN
    IF TG_OP='UPDATE' AND (to_jsonb(NEW)-'created_by_id')=(to_jsonb(OLD)-'created_by_id')
       AND NEW.created_by_id IS NULL THEN RETURN NEW; END IF;
    SELECT EXISTS(SELECT 1 FROM events_eventpage WHERE id=OLD.page_id) INTO alive;
  ELSIF TG_TABLE_NAME IN ('events_eventsessionidentity','events_eventsessionalias') THEN
    SELECT EXISTS(SELECT 1 FROM events_eventpage WHERE id=OLD.page_id) INTO alive;
  ELSE
    IF TG_TABLE_NAME='events_eventpagerevisionmember' AND TG_OP='UPDATE'
       AND (to_jsonb(NEW)-'profile_id')=(to_jsonb(OLD)-'profile_id')
       AND NEW.profile_id IS NULL THEN RETURN NEW; END IF;
    SELECT EXISTS(SELECT 1 FROM events_eventpagerevision WHERE id=OLD.revision_id) INTO alive;
  END IF;
  IF TG_OP='DELETE' AND NOT alive THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'Website history and session reservations are immutable' USING ERRCODE='23514';
END $$;

CREATE FUNCTION event_snapshot_final() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p events_eventpage; r events_eventpagerevision; rid uuid; expected jsonb; actual jsonb;
BEGIN
  IF TG_TABLE_NAME='events_eventpage' THEN
    SELECT * INTO p FROM events_eventpage WHERE id=NEW.id;
    IF NOT FOUND THEN RETURN NULL; END IF;
    IF (p.draft_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventpagerevision
        WHERE id=p.draft_revision_id AND page_id=p.id)) OR
       (p.published_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventpagerevision
        WHERE id=p.published_revision_id AND page_id=p.id)) OR
       (p.released AND (p.published_revision_id IS NULL OR p.draft_revision_id IS NULL)) THEN
      RAISE EXCEPTION 'Website pointers/release are invalid' USING ERRCODE='23514';
    END IF;
  ELSIF TG_TABLE_NAME='events_eventsession' THEN
    IF EXISTS (SELECT 1 FROM events_eventsession s WHERE s.id=NEW.id AND NOT EXISTS (
      SELECT 1 FROM events_eventsessionidentity i WHERE i.id=s.identity_id AND i.page_id=s.page_id)) OR
      EXISTS (SELECT 1 FROM events_eventsession s WHERE s.id=NEW.id AND NOT EXISTS (
      SELECT 1 FROM events_eventsessionalias a WHERE a.identity_id=s.identity_id AND a.page_id=s.page_id AND a.slug=s.slug)) THEN
      RAISE EXCEPTION 'Session identity belongs to another page' USING ERRCODE='23514';
    END IF;
  ELSIF TG_TABLE_NAME='events_eventsessionalias' THEN
    IF NOT EXISTS (SELECT 1 FROM events_eventsessionidentity WHERE id=NEW.identity_id AND page_id=NEW.page_id) THEN
      RAISE EXCEPTION 'Alias identity belongs to another page' USING ERRCODE='23514';
    END IF;
  ELSE
    IF TG_TABLE_NAME='events_eventpagerevision' THEN rid:=NEW.id; ELSE rid:=NEW.revision_id; END IF;
    SELECT * INTO r FROM events_eventpagerevision WHERE id=rid;
    IF NOT FOUND THEN RETURN NULL; END IF;
    IF r.schema_version<>1 THEN RAISE EXCEPTION 'Unsupported website snapshot version' USING ERRCODE='23514'; END IF;
    IF EXISTS (SELECT 1 FROM events_eventpagerevisionasset x JOIN events_eventpageasset a ON a.id=x.asset_id
               WHERE x.revision_id=rid AND a.page_id<>r.page_id) OR EXISTS (
      SELECT 1 FROM jsonb_array_elements(r.document->'sessions') s WHERE NOT EXISTS (
        SELECT 1 FROM events_eventsessionidentity i JOIN events_eventsessionalias a ON a.identity_id=i.id
          WHERE i.id=(s->>'session_id')::uuid AND i.page_id=r.page_id AND a.page_id=r.page_id AND a.slug=s->>'slug')) THEN
      RAISE EXCEPTION 'Snapshot identity/asset belongs to another page' USING ERRCODE='23514';
    END IF;
    SELECT coalesce(jsonb_object_agg(slot, aid), '{}'::jsonb) INTO expected FROM (
      SELECT 'section:'||(s->>'slug') AS slot, (s->>'asset_id')::bigint AS aid
        FROM jsonb_array_elements(r.document->'sections') s WHERE s->>'asset_id' IS NOT NULL
      UNION ALL SELECT 'editorial:cover', (r.document->'editorial_document'->>'cover_asset_id')::bigint
        WHERE r.document->'editorial_document'->>'cover_asset_id' IS NOT NULL
      UNION ALL SELECT 'editorial:'||(s->>'id')||':'||(ordinal-1)::text, (item->>'asset_id')::bigint
        FROM jsonb_array_elements(r.document->'editorial_document'->'sections') s,
        LATERAL jsonb_array_elements(s->'payload'->'items') WITH ORDINALITY x(item,ordinal)
        WHERE s->>'type'='gallery'
    ) slots;
    SELECT coalesce(jsonb_object_agg(slot, asset_id), '{}'::jsonb) INTO actual
      FROM events_eventpagerevisionasset WHERE revision_id=rid;
    IF expected<>actual THEN RAISE EXCEPTION 'Snapshot asset references incomplete' USING ERRCODE='23514'; END IF;
    SELECT coalesce(jsonb_agg(slot ORDER BY slot), '[]'::jsonb) INTO expected FROM (
      SELECT item->>'member_slot_id' AS slot FROM jsonb_array_elements(r.document->'editorial_document'->'sections') s,
        LATERAL jsonb_array_elements(s->'payload'->'entries') item WHERE s->>'type'='team' AND item->>'kind'='member'
    ) slots;
    SELECT coalesce(jsonb_agg(slot::text ORDER BY slot::text), '[]'::jsonb) INTO actual
      FROM events_eventpagerevisionmember WHERE revision_id=rid;
    IF expected<>actual THEN RAISE EXCEPTION 'Snapshot member references incomplete' USING ERRCODE='23514'; END IF;
  END IF;
  RETURN NULL;
END $$;

CREATE FUNCTION event_snapshot_windows() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p events_eventpage; r events_eventpagerevision; lo timestamptz; hi timestamptz;
        e events_event; s jsonb; x timestamptz; y timestamptz;
        target_event_id bigint; target_series_id bigint; target_old_series_id bigint; target_page_id bigint;
BEGIN
  -- Lock the owner before examining its final publication; service writers use
  -- series -> occurrence -> tenant -> authority -> page in the same transaction.
  IF TG_TABLE_NAME='events_eventpage' THEN
    IF TG_OP='DELETE' THEN target_page_id:=OLD.id; target_event_id:=OLD.event_id; target_series_id:=OLD.series_id;
    ELSE target_page_id:=NEW.id; target_event_id:=NEW.event_id; target_series_id:=NEW.series_id; END IF;
  ELSIF TG_TABLE_NAME='events_eventseries' THEN
    IF TG_OP='DELETE' THEN target_series_id:=OLD.id; ELSE target_series_id:=NEW.id; END IF;
  ELSE
    IF TG_OP<>'INSERT' THEN target_old_series_id:=OLD.series_id; END IF;
    IF TG_OP='DELETE' THEN target_event_id:=OLD.id; ELSE target_event_id:=NEW.id; target_series_id:=NEW.series_id; END IF;
  END IF;
  IF TG_TABLE_NAME='events_eventpage' AND target_event_id IS NOT NULL THEN
    SELECT events_event.series_id INTO target_series_id FROM events_event WHERE id=target_event_id;
  END IF;
  FOR p IN SELECT ep.* FROM events_eventpage ep WHERE ep.released AND ep.published_revision_id IS NOT NULL
    AND (ep.id=target_page_id OR ep.event_id=target_event_id OR ep.series_id=target_series_id OR ep.series_id=target_old_series_id)
    ORDER BY ep.id LOOP
    SELECT * INTO r FROM events_eventpagerevision WHERE id=p.published_revision_id;
    IF p.series_id IS NOT NULL THEN
      SELECT event_website_wall_start(dtstart_local_date+dtstart_local_time, recurrence_timezone),
        event_website_wall_start(dtstart_local_date+dtstart_local_time, recurrence_timezone)+duration_minutes*interval '1 minute'
        INTO lo,hi FROM events_eventseries WHERE id=p.series_id FOR NO KEY UPDATE;
    ELSE
      SELECT starts_at,ends_at INTO lo,hi FROM events_event WHERE id=p.event_id FOR NO KEY UPDATE;
    END IF;
    FOR s IN SELECT value FROM jsonb_array_elements(r.document->'sessions')
      WHERE value->>'visibility'='published'
        AND coalesce((r.document->'section_enabled'->>'SCHEDULE')::boolean, true) LOOP
      x:=(s->>'starts_at')::timestamptz; y:=(s->>'ends_at')::timestamptz;
      IF x<lo OR y>hi OR y<=x THEN
        RAISE EXCEPTION 'Owner window excludes released snapshot' USING ERRCODE='23514';
      END IF;
      IF p.series_id IS NOT NULL THEN
        FOR e IN SELECT * FROM events_event WHERE events_event.series_id=p.series_id AND NOT EXISTS (
          SELECT 1 FROM events_eventpage own WHERE own.event_id=events_event.id)
          ORDER BY events_event.id FOR NO KEY UPDATE LOOP
          IF x-r.source_anchor_start<interval '0' OR y-r.source_anchor_start>e.ends_at-e.starts_at THEN
            RAISE EXCEPTION 'Occurrence window excludes released snapshot' USING ERRCODE='23514';
          END IF;
        END LOOP;
      END IF;
    END LOOP;
  END LOOP;
  RETURN NULL;
END $$;
"""

IMMUTABLE = ("eventpagerevision", "eventpagerevisionasset", "eventpagerevisionmember", "eventsessionidentity", "eventsessionalias")
FINAL = ("eventpage", "eventpagerevision", "eventpagerevisionasset", "eventpagerevisionmember", "eventsession", "eventsessionalias")
# Column-scoped: only window inputs re-check (and lock) publications. A status or
# image write on one occurrence must not lock its series and sibling occurrences
# at commit, or concurrent cancels and series edits deadlock.
WINDOWS = {
    "eventpage": "INSERT OR UPDATE OR DELETE",
    "event": "INSERT OR DELETE OR UPDATE OF starts_at, ends_at, series_id",
    "eventseries": ("INSERT OR DELETE OR UPDATE OF dtstart_local_date, dtstart_local_time, "
                    "recurrence_timezone, duration_minutes"),
}


class Migration(migrations.Migration):
    dependencies = [("events", "0038_website_snapshot_backfill")]
    # Commit the 0038 backfill before altering its FK: populated upgrades otherwise
    # have deferred identity FK checks pending when PostgreSQL executes the DDL.
    operations = [migrations.AlterField(
        model_name="eventsession", name="identity", field=models.OneToOneField(
            "events.eventsessionidentity", on_delete=models.RESTRICT, related_name="working_session")),
        migrations.RunSQL(SQL + "\n".join(
        f"CREATE TRIGGER event_snapshot_immutable BEFORE UPDATE OR DELETE ON events_{table} "
        "FOR EACH ROW EXECUTE FUNCTION event_snapshot_immutable();" for table in IMMUTABLE
    ) + "\n" + "\n".join(
        f"CREATE CONSTRAINT TRIGGER event_snapshot_final AFTER INSERT OR UPDATE ON events_{table} "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION event_snapshot_final();" for table in FINAL
    ) + "\n" + "\n".join(
        f"CREATE CONSTRAINT TRIGGER event_snapshot_windows AFTER {events} ON events_{table} "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION event_snapshot_windows();"
        for table, events in WINDOWS.items()
    ), "\n".join(
        f"DROP TRIGGER event_snapshot_{name} ON events_{table};" for name, tables in
        (("immutable", IMMUTABLE), ("final", FINAL), ("windows", WINDOWS)) for table in tables
    ) + "\nDROP TRIGGER event_asset_immutable ON events_eventpageasset; DROP FUNCTION event_asset_immutable();"
      + "\nDROP FUNCTION event_snapshot_immutable(); DROP FUNCTION event_snapshot_final(); DROP FUNCTION event_snapshot_windows();")]
