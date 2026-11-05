"""#178 backfill and Postgres backstops for submission stages.

- Every existing hackathon config becomes ONE stage, "Submission", copied from its window
  (opens_at, deadline, grace minutes, late policy) with files and links both accepted, so every
  existing event behaves exactly as before ("Single submission").
- Every existing frozen snapshot is recorded as a snapshot of that stage, and every project that has
  ever submitted gets its stage entry pointing at today's current snapshot, with today's triage.
- Snapshot-stage records, shortlists, their entries and announcements, and deadline extensions are
  append-only (the L21b history guard); same-event scope checks back the model rules.
"""
from django.db import migrations

APPEND_ONLY = ("events_snapshotstage", "events_stageshortlist", "events_stageshortlistentry",
               "events_stageshortlistannouncement", "events_stageextension")

SCOPE = r"""
CREATE FUNCTION events_stage_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'events_submissionstageentry' THEN
    IF NOT EXISTS (SELECT 1 FROM events_submissionstage s JOIN events_hackathonsubmission p ON p.event_id=s.event_id
                   WHERE s.id=NEW.stage_id AND p.id=NEW.submission_id) THEN
      RAISE EXCEPTION 'submission stage event mismatch'; END IF;
    IF NEW.current_snapshot_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot n
        WHERE n.id=NEW.current_snapshot_id AND n.submission_id=NEW.submission_id) THEN
      RAISE EXCEPTION 'stage snapshot owner mismatch'; END IF;
  ELSIF TG_TABLE_NAME = 'events_snapshotstage' THEN
    IF NOT EXISTS (SELECT 1 FROM events_submissionstage s JOIN events_hackathonsubmission p ON p.event_id=s.event_id
                   JOIN events_submissionsnapshot n ON n.submission_id=p.id WHERE s.id=NEW.stage_id AND n.id=NEW.snapshot_id) THEN
      RAISE EXCEPTION 'snapshot stage event mismatch'; END IF;
  ELSIF TG_TABLE_NAME = 'events_stageshortlist' THEN
    IF NOT EXISTS (SELECT 1 FROM events_submissionstage s WHERE s.id=NEW.stage_id AND s.event_id=NEW.event_id)
       OR (NEW.source_round_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judginground r
           WHERE r.id=NEW.source_round_id AND r.event_id=NEW.event_id)) THEN
      RAISE EXCEPTION 'shortlist event mismatch'; END IF;
  ELSIF TG_TABLE_NAME = 'events_stageshortlistentry' THEN
    IF NOT EXISTS (SELECT 1 FROM events_stageshortlist l JOIN events_hackathonsubmission p ON p.event_id=l.event_id
                   JOIN events_submissionsnapshot n ON n.submission_id=p.id
                   WHERE l.id=NEW.shortlist_id AND p.id=NEW.submission_id AND n.id=NEW.snapshot_id) THEN
      RAISE EXCEPTION 'shortlist entry event mismatch'; END IF;
  ELSIF TG_TABLE_NAME = 'events_stageshortlistannouncement' THEN
    IF NOT EXISTS (SELECT 1 FROM events_stageshortlist l WHERE l.id=NEW.shortlist_id AND l.event_id=NEW.event_id) THEN
      RAISE EXCEPTION 'shortlist announcement event mismatch'; END IF;
  ELSIF TG_TABLE_NAME = 'events_stageextension' THEN
    IF NOT EXISTS (SELECT 1 FROM events_submissionstage s JOIN events_hackathonteam t ON t.event_id=s.event_id
                   WHERE s.id=NEW.stage_id AND t.id=NEW.team_id) THEN
      RAISE EXCEPTION 'stage extension event mismatch'; END IF;
  ELSIF TG_TABLE_NAME = 'events_judginground' THEN
    IF NEW.submission_stage_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionstage s
        WHERE s.id=NEW.submission_stage_id AND s.event_id=NEW.event_id) THEN
      RAISE EXCEPTION 'round stage event mismatch'; END IF;
  END IF;
  RETURN NEW;
END;
$$;
"""
SCOPED = ("events_submissionstageentry", "events_snapshotstage", "events_stageshortlist", "events_stageshortlistentry",
          "events_stageshortlistannouncement", "events_stageextension", "events_judginground")

FORWARD_SQL = SCOPE + "".join(
    f"CREATE TRIGGER {t}_stage_scope BEFORE INSERT OR UPDATE ON {t} FOR EACH ROW "
    "EXECUTE FUNCTION events_stage_scope_guard();\n" for t in SCOPED) + "".join(
    f"CREATE TRIGGER {t}_programme_history BEFORE UPDATE OR DELETE ON {t} FOR EACH ROW "
    "EXECUTE FUNCTION events_l21b_history_guard();\n" for t in APPEND_ONLY)
REVERSE_SQL = "".join(f"DROP TRIGGER IF EXISTS {t}_programme_history ON {t};\n" for t in APPEND_ONLY) + "".join(
    f"DROP TRIGGER IF EXISTS {t}_stage_scope ON {t};\n" for t in SCOPED) + "DROP FUNCTION IF EXISTS events_stage_scope_guard();\n"


def single_submission_stage(apps, schema_editor):
    """Each existing window becomes stage 1; each existing snapshot becomes a snapshot of that stage."""
    Config = apps.get_model("events", "HackathonConfig")
    Stage = apps.get_model("events", "SubmissionStage")
    Entry = apps.get_model("events", "SubmissionStageEntry")
    SnapshotStage = apps.get_model("events", "SnapshotStage")
    Submission = apps.get_model("events", "HackathonSubmission")
    Snapshot = apps.get_model("events", "SubmissionSnapshot")
    staged = set(Stage.objects.values_list("event_id", flat=True))
    for config in Config.objects.order_by("pk").iterator():
        if config.event_id in staged:
            continue
        stage = Stage.objects.create(
            event_id=config.event_id, position=1, name="Submission", opens_at=config.submission_opens_at,
            deadline=config.submission_deadline, grace_minutes=config.submission_grace_minutes,
            late_policy=config.late_policy, content_mode="files_and_links")
        for project in Submission.objects.filter(event_id=config.event_id).order_by("pk").iterator():
            snapshot_ids = list(Snapshot.objects.filter(submission_id=project.pk).order_by("pk").values_list("pk", flat=True))
            if not snapshot_ids and project.current_snapshot_id is None:
                continue
            SnapshotStage.objects.bulk_create([SnapshotStage(snapshot_id=pk, stage_id=stage.pk) for pk in snapshot_ids])
            Entry.objects.create(submission_id=project.pk, stage_id=stage.pk, current_snapshot_id=project.current_snapshot_id,
                                 submitted_at=project.submitted_at, triage=project.triage)


class Migration(migrations.Migration):
    dependencies = [("events", "0069_submission_stages")]
    operations = [
        migrations.RunPython(single_submission_stage, migrations.RunPython.noop),
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
