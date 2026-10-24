"""Selector IDs are typed stage references, never a cross-event lookup escape."""
from django.db import migrations

FORWARD = """
CREATE FUNCTION events_stage_selector_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.form_key='stage' AND NOT EXISTS (
    SELECT 1 FROM events_eventstageform s WHERE s.id=NEW.selector_id AND s.event_id=NEW.event_id
  ) THEN RAISE EXCEPTION 'stage form selector ownership mismatch'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER event_form_stage_selector BEFORE INSERT ON events_eventformrevision
  FOR EACH ROW EXECUTE FUNCTION events_stage_selector_guard();

CREATE FUNCTION events_attendance_correction_watermark_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
CREATE TRIGGER event_attendance_correction_watermark BEFORE INSERT ON events_eventattendancecorrection
  FOR EACH ROW EXECUTE FUNCTION events_attendance_correction_watermark_guard();
"""
REVERSE = """
DROP TRIGGER event_attendance_correction_watermark ON events_eventattendancecorrection;
DROP FUNCTION events_attendance_correction_watermark_guard();
DROP TRIGGER event_form_stage_selector ON events_eventformrevision;
DROP FUNCTION events_stage_selector_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0054_reimbursement_guards")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
