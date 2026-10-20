"""A historical attendance correction may arrive by tenant import after later check-ins.

The live guard pins a new correction to the registration's current attendance
revision. An imported correction is history: its registration may have been checked
in again afterwards, so only its own check-in/registration/event identity is checked
while the importer's transaction-local ``app.tenant_import`` flag is set.
"""
from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION events_attendance_correction_watermark_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM events_eventcheckinevent c
    WHERE c.id=NEW.invalidated_through_checkin_id AND c.registration_id=NEW.registration_id
      AND c.event_id=NEW.event_id)
    THEN RAISE EXCEPTION 'attendance correction watermark mismatch'; END IF;
  IF COALESCE(current_setting('app.tenant_import', true), '') <> 'on' AND NOT EXISTS (
    SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id
    AND r.attendance_revision=NEW.attendance_revision)
    THEN RAISE EXCEPTION 'attendance correction revision mismatch'; END IF;
  RETURN NEW;
END; $$;
"""
REVERSE = """
CREATE OR REPLACE FUNCTION events_attendance_correction_watermark_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM events_eventcheckinevent c
    WHERE c.id=NEW.invalidated_through_checkin_id AND c.registration_id=NEW.registration_id
      AND c.event_id=NEW.event_id)
    THEN RAISE EXCEPTION 'attendance correction watermark mismatch'; END IF;
  IF NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id
    AND r.attendance_revision=NEW.attendance_revision)
    THEN RAISE EXCEPTION 'attendance correction revision mismatch'; END IF;
  RETURN NEW;
END; $$;
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0051_stage_runtime")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
