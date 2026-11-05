"""L21b backstops and the C-37 options backfill.

- Finalist advances, finalists, their announcements and prize payouts are append-only in Postgres,
  with same-event scope checks (a payout's award, prize and space belong to its event).
- Every EXISTING event gets an options row with today's two emails ON (results announcement and
  submission receipt), so nothing it already does changes; events created later have no row, so both
  switches start OFF (#128 C-37). The finalists email is new and stays off everywhere.
"""
from django.db import migrations

HISTORY = r"""
CREATE FUNCTION events_l21b_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
"""
TABLES = ("events_finalistadvance", "events_judgingfinalist", "events_finalistannouncement", "events_hackathonprizepayout")
SCOPE = r"""
CREATE FUNCTION events_finalistadvance_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM events_judginground r WHERE r.id=NEW.source_round_id AND r.event_id=NEW.event_id)
     OR NOT EXISTS (SELECT 1 FROM events_judginground r WHERE r.id=NEW.target_round_id AND r.event_id=NEW.event_id)
    THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_finalistadvance_programme_scope BEFORE INSERT ON events_finalistadvance FOR EACH ROW EXECUTE FUNCTION events_finalistadvance_scope_guard();
CREATE FUNCTION events_hackathonprizepayout_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
CREATE TRIGGER events_hackathonprizepayout_programme_scope BEFORE INSERT ON events_hackathonprizepayout FOR EACH ROW EXECUTE FUNCTION events_hackathonprizepayout_scope_guard();
"""
FORWARD_SQL = HISTORY + SCOPE + "".join(
    f"CREATE TRIGGER {t}_programme_history BEFORE UPDATE OR DELETE ON {t} FOR EACH ROW "
    "EXECUTE FUNCTION events_l21b_history_guard();\n" for t in TABLES)
REVERSE_SQL = "".join(f"DROP TRIGGER IF EXISTS {t}_programme_history ON {t};\n" for t in TABLES) + """
DROP TRIGGER IF EXISTS events_hackathonprizepayout_programme_scope ON events_hackathonprizepayout;
DROP TRIGGER IF EXISTS events_finalistadvance_programme_scope ON events_finalistadvance;
DROP FUNCTION IF EXISTS events_hackathonprizepayout_scope_guard();
DROP FUNCTION IF EXISTS events_finalistadvance_scope_guard();
DROP FUNCTION IF EXISTS events_l21b_history_guard();
"""


def keep_existing_emails(apps, schema_editor):
    """Existing events keep today's behaviour: both hackathon emails stay on."""
    Event = apps.get_model("events", "Event")
    Options = apps.get_model("events", "HackathonProgrammeOptions")
    have = set(Options.objects.values_list("event_id", flat=True))
    rows = [Options(event_id=pk, results_email=True, submission_receipt_email=True)
            for pk in Event.objects.order_by("pk").values_list("pk", flat=True).iterator() if pk not in have]
    Options.objects.bulk_create(rows, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("events", "0067_l21b_judging_money")]
    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
        migrations.RunPython(keep_existing_emails, migrations.RunPython.noop),
    ]
