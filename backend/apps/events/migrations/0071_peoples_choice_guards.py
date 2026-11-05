"""People's choice (#181 S3) database backstops.

- The published result and its standings are append-only (the L21b history guard, which still lets the
  explicit lifecycle purge delete them).
- Same-event scope: a ballot's team and void reason, the config's and result's prize, and every
  standing's snapshot belong to the row's own event.
- The L21b prize-payout scope guard is replaced so a payout may point at a People's choice winning
  standing instead of a judged award; the judged-award branch is unchanged.
"""
from django.db import migrations

APPEND_ONLY = ("events_peopleschoiceresult", "events_peopleschoicestanding")

SCOPE = r"""
CREATE FUNCTION events_peopleschoice_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'events_peopleschoicevote' THEN
    IF NOT EXISTS (SELECT 1 FROM events_hackathonteam t WHERE t.id=NEW.team_id AND t.event_id=NEW.event_id)
      THEN RAISE EXCEPTION 'peoples choice team event mismatch'; END IF;
    IF NEW.void_reason_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM events_judgingreason r WHERE r.id=NEW.void_reason_id AND r.event_id=NEW.event_id)
      THEN RAISE EXCEPTION 'peoples choice reason event mismatch'; END IF;
  ELSIF TG_TABLE_NAME = 'events_peopleschoicestanding' THEN
    IF NOT EXISTS (SELECT 1 FROM events_peopleschoiceresult r
                   JOIN events_submissionsnapshot s ON s.id=NEW.submission_snapshot_id
                   JOIN events_hackathonsubmission h ON h.id=s.submission_id
                   WHERE r.id=NEW.result_id AND h.event_id=r.event_id)
      THEN RAISE EXCEPTION 'peoples choice standing event mismatch'; END IF;
  ELSIF NEW.prize_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM events_hackathonprize p WHERE p.id=NEW.prize_id AND p.event_id=NEW.event_id) THEN
    RAISE EXCEPTION 'peoples choice prize event mismatch';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_peopleschoicevote_programme_scope BEFORE INSERT OR UPDATE ON events_peopleschoicevote
  FOR EACH ROW EXECUTE FUNCTION events_peopleschoice_scope_guard();
CREATE TRIGGER events_peopleschoiceconfig_programme_scope BEFORE INSERT OR UPDATE ON events_peopleschoiceconfig
  FOR EACH ROW EXECUTE FUNCTION events_peopleschoice_scope_guard();
CREATE TRIGGER events_peopleschoiceresult_programme_scope BEFORE INSERT ON events_peopleschoiceresult
  FOR EACH ROW EXECUTE FUNCTION events_peopleschoice_scope_guard();
CREATE TRIGGER events_peopleschoicestanding_programme_scope BEFORE INSERT ON events_peopleschoicestanding
  FOR EACH ROW EXECUTE FUNCTION events_peopleschoice_scope_guard();
"""

PAYOUT_SCOPE = r"""
CREATE OR REPLACE FUNCTION events_hackathonprizepayout_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM events_event WHERE id=NEW.event_id AND makerspace_id=NEW.makerspace_id)
    THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NOT EXISTS (SELECT 1 FROM events_hackathonprize p WHERE p.id=NEW.prize_id AND p.event_id=NEW.event_id)
    THEN RAISE EXCEPTION 'prize payout event mismatch'; END IF;
  IF NEW.award_id IS NOT NULL THEN
    IF NOT EXISTS (SELECT 1 FROM events_eventaward a JOIN events_eventresultrevision r ON r.id=a.result_id
                   WHERE a.id=NEW.award_id AND r.event_id=NEW.event_id AND a.prize_id=NEW.prize_id)
      THEN RAISE EXCEPTION 'prize payout event mismatch'; END IF;
  ELSIF NOT EXISTS (SELECT 1 FROM events_peopleschoicestanding s JOIN events_peopleschoiceresult r ON r.id=s.result_id
                    WHERE s.id=NEW.peoples_choice_standing_id AND s.winner AND r.event_id=NEW.event_id
                      AND r.prize_id=NEW.prize_id) THEN
    RAISE EXCEPTION 'prize payout event mismatch';
  END IF;
  RETURN NEW;
END;
$$;
"""

# The L21b body, restored on reverse.
PAYOUT_SCOPE_L21B = r"""
CREATE OR REPLACE FUNCTION events_hackathonprizepayout_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM events_event WHERE id=NEW.event_id AND makerspace_id=NEW.makerspace_id)
    THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NOT EXISTS (SELECT 1 FROM events_hackathonprize p WHERE p.id=NEW.prize_id AND p.event_id=NEW.event_id)
     OR NOT EXISTS (SELECT 1 FROM events_eventaward a JOIN events_eventresultrevision r ON r.id=a.result_id
                    WHERE a.id=NEW.award_id AND r.event_id=NEW.event_id AND a.prize_id=NEW.prize_id)
    THEN RAISE EXCEPTION 'prize payout event mismatch'; END IF;
  RETURN NEW;
END;
$$;
"""

FORWARD_SQL = SCOPE + PAYOUT_SCOPE + "".join(
    f"CREATE TRIGGER {t}_programme_history BEFORE UPDATE OR DELETE ON {t} FOR EACH ROW "
    "EXECUTE FUNCTION events_l21b_history_guard();\n" for t in APPEND_ONLY)
REVERSE_SQL = "".join(f"DROP TRIGGER IF EXISTS {t}_programme_history ON {t};\n" for t in APPEND_ONLY) + "".join(
    f"DROP TRIGGER IF EXISTS events_{name}_programme_scope ON events_{name};\n"
    for name in ("peopleschoicevote", "peopleschoiceconfig", "peopleschoiceresult", "peopleschoicestanding")
) + "DROP FUNCTION IF EXISTS events_peopleschoice_scope_guard();\n" + PAYOUT_SCOPE_L21B


class Migration(migrations.Migration):
    dependencies = [("events", "0070_peoples_choice")]
    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
