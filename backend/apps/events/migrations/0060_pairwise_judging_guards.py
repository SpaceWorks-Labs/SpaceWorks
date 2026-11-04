"""Pairwise judging backstops: same-event FK paths, pair shape, open round, append-only history."""
from django.db import migrations

FORWARD_SQL = r"""
CREATE FUNCTION events_judgepairwisecomparison_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NOT EXISTS (SELECT 1 FROM events_judginground r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  IF NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.judge_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme judge event mismatch'; END IF;
  IF EXISTS (SELECT 1 FROM events_judgeassignment a WHERE a.id IN (NEW.previous_id, NEW.current_id)
      AND (a.round_id<>NEW.round_id OR a.judge_role_assignment_id<>NEW.judge_id OR a.event_id<>owner_event))
    THEN RAISE EXCEPTION 'pairwise comparison assignment mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgepairwisecomparison_programme_scope BEFORE INSERT OR UPDATE ON events_judgepairwisecomparison FOR EACH ROW EXECUTE FUNCTION events_judgepairwisecomparison_scope_guard();
CREATE FUNCTION events_judgepairwisecomparison_open_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE round_state text; round_mode text; restoring boolean;
BEGIN
  SELECT r.state,r.mode,m.lifecycle_state='importing' INTO round_state,round_mode,restoring FROM events_judginground r
    JOIN events_event e ON e.id=r.event_id JOIN makerspaces_makerspace m ON m.id=e.makerspace_id WHERE r.id=NEW.round_id;
  IF round_mode IS DISTINCT FROM 'pairwise' THEN RAISE EXCEPTION 'comparison requires a pairwise round'; END IF;
  IF round_state<>'open' AND NOT restoring THEN RAISE EXCEPTION 'pairwise round is not open'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgepairwisecomparison_programme_open BEFORE INSERT ON events_judgepairwisecomparison FOR EACH ROW EXECUTE FUNCTION events_judgepairwisecomparison_open_guard();
CREATE FUNCTION events_judgepairwisecomparison_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['notes']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_judgepairwisecomparison_programme_history BEFORE UPDATE OR DELETE ON events_judgepairwisecomparison FOR EACH ROW EXECUTE FUNCTION events_judgepairwisecomparison_history_guard();
CREATE FUNCTION events_judgepairwisecomparison_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_judgepairwisecomparison_programme_pii_fence BEFORE INSERT OR UPDATE ON events_judgepairwisecomparison FOR EACH ROW EXECUTE FUNCTION events_judgepairwisecomparison_pii_fence_guard();
CREATE FUNCTION events_judgepairwiseinvalidation_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM events_judgepairwisecomparison c JOIN events_judgingreason r ON r.event_id=c.event_id
      WHERE c.id=NEW.comparison_id AND r.id=NEW.reason_id) THEN RAISE EXCEPTION 'programme reason event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgepairwiseinvalidation_programme_scope BEFORE INSERT OR UPDATE ON events_judgepairwiseinvalidation FOR EACH ROW EXECUTE FUNCTION events_judgepairwiseinvalidation_scope_guard();
CREATE FUNCTION events_judgepairwiseinvalidation_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_judgepairwiseinvalidation_programme_history BEFORE UPDATE OR DELETE ON events_judgepairwiseinvalidation FOR EACH ROW EXECUTE FUNCTION events_judgepairwiseinvalidation_history_guard();
CREATE FUNCTION events_judgepairwisecursor_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NOT EXISTS (SELECT 1 FROM events_judginground r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  IF NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.judge_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme judge event mismatch'; END IF;
  IF EXISTS (SELECT 1 FROM events_judgeassignment a WHERE a.id IN (NEW.previous_id, NEW.current_id)
      AND (a.round_id<>NEW.round_id OR a.judge_role_assignment_id<>NEW.judge_id))
    THEN RAISE EXCEPTION 'pairwise cursor assignment mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgepairwisecursor_programme_scope BEFORE INSERT OR UPDATE ON events_judgepairwisecursor FOR EACH ROW EXECUTE FUNCTION events_judgepairwisecursor_scope_guard();
"""

REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS events_judgepairwisecursor_programme_scope ON events_judgepairwisecursor;
DROP TRIGGER IF EXISTS events_judgepairwiseinvalidation_programme_history ON events_judgepairwiseinvalidation;
DROP TRIGGER IF EXISTS events_judgepairwiseinvalidation_programme_scope ON events_judgepairwiseinvalidation;
DROP TRIGGER IF EXISTS events_judgepairwisecomparison_programme_pii_fence ON events_judgepairwisecomparison;
DROP TRIGGER IF EXISTS events_judgepairwisecomparison_programme_history ON events_judgepairwisecomparison;
DROP TRIGGER IF EXISTS events_judgepairwisecomparison_programme_open ON events_judgepairwisecomparison;
DROP TRIGGER IF EXISTS events_judgepairwisecomparison_programme_scope ON events_judgepairwisecomparison;
DROP FUNCTION IF EXISTS events_judgepairwisecursor_scope_guard();
DROP FUNCTION IF EXISTS events_judgepairwiseinvalidation_history_guard();
DROP FUNCTION IF EXISTS events_judgepairwiseinvalidation_scope_guard();
DROP FUNCTION IF EXISTS events_judgepairwisecomparison_pii_fence_guard();
DROP FUNCTION IF EXISTS events_judgepairwisecomparison_history_guard();
DROP FUNCTION IF EXISTS events_judgepairwisecomparison_open_guard();
DROP FUNCTION IF EXISTS events_judgepairwisecomparison_scope_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0059_pairwise_judging")]
    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
