"""Migration SQL supplied to G; this lane creates no migration or app hook.

G installs after A/B/D tables, in the same migration as the model graph. These
guards protect bulk/SQL writers too; model.save is not an immutability boundary.
"""

IMMUTABLE_TABLES = ("events_submissionsnapshot", "events_snapshotasset", "events_snapshotlink",
                    "events_snapshottrack", "events_snapshotprize")

IMMUTABLE_FUNCTION = """
CREATE OR REPLACE FUNCTION events_submission_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' AND current_setting('app.allow_immutable_delete', true) = 'on' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'submission snapshot is immutable';
END;
$$ LANGUAGE plpgsql;
"""

ASSET_FUNCTION = """
CREATE OR REPLACE FUNCTION events_submission_asset_guard() RETURNS trigger AS $$
DECLARE owner_event bigint; owner_team bigint;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF current_setting('app.allow_immutable_delete', true) = 'on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'submission asset metadata is retained';
  END IF;
  IF TG_TABLE_NAME = 'events_submissionasset' THEN
    SELECT event_id, team_id INTO owner_event, owner_team
      FROM events_hackathonsubmission WHERE id = NEW.submission_id;
    IF owner_event IS DISTINCT FROM NEW.event_id OR owner_team IS DISTINCT FROM NEW.team_id THEN
      RAISE EXCEPTION 'submission asset owner mismatch';
    END IF;
  END IF;
  IF TG_OP = 'UPDATE' AND (OLD.ready_at IS NOT NULL OR OLD.sha256 <> '') AND
    (NEW.sha256, NEW.original_sha256, NEW.actual_bytes, NEW.canonical_mime, NEW.object_key,
     NEW.final_version_id, NEW.event_id, NEW.public_id, NEW.generation)
    IS DISTINCT FROM
    (OLD.sha256, OLD.original_sha256, OLD.actual_bytes, OLD.canonical_mime, OLD.object_key,
     OLD.final_version_id, OLD.event_id, OLD.public_id, OLD.generation) THEN
    RAISE EXCEPTION 'ready submission asset content is immutable';
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.expired_at IS NOT NULL AND NEW.expired_at IS NULL THEN
    RAISE EXCEPTION 'expired submission asset cannot revive';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

REFERENCE_FUNCTION = """
CREATE OR REPLACE FUNCTION events_snapshot_reference_guard() RETURNS trigger AS $$
DECLARE owning_submission bigint; owning_event bigint; owning_team bigint; valid boolean;
BEGIN
  SELECT s.id, s.event_id, s.team_id INTO owning_submission, owning_event, owning_team
    FROM events_submissionsnapshot snap JOIN events_hackathonsubmission s ON s.id=snap.submission_id
    WHERE snap.id=NEW.snapshot_id;
  IF TG_TABLE_NAME='events_snapshotasset' THEN
    SELECT (submission_id=owning_submission AND event_id=owning_event AND team_id=owning_team
      AND state='ready' AND scan_status IN ('clean','skipped') AND expired_at IS NULL
      AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)) INTO valid
      FROM events_submissionasset WHERE id=NEW.asset_id;
  ELSIF TG_TABLE_NAME='events_snapshotlink' THEN
    SELECT submission_id=owning_submission INTO valid FROM events_submissionlink WHERE id=NEW.link_id;
  ELSIF TG_TABLE_NAME='events_snapshottrack' THEN
    SELECT event_id=owning_event INTO valid FROM events_hackathontrack WHERE id=NEW.track_id;
  ELSIF TG_TABLE_NAME='events_snapshotprize' THEN
    SELECT event_id=owning_event INTO valid FROM events_hackathonprize WHERE id=NEW.prize_id;
  END IF;
  IF valid IS DISTINCT FROM TRUE THEN RAISE EXCEPTION 'snapshot reference owner mismatch'; END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

PROJECT_FUNCTION = """
CREATE OR REPLACE FUNCTION events_submission_project_guard() RETURNS trigger AS $$
DECLARE owning_event bigint; owning_submission bigint;
BEGIN
  SELECT event_id INTO owning_event FROM events_hackathonteam WHERE id=NEW.team_id;
  IF owning_event IS DISTINCT FROM NEW.event_id THEN
    RAISE EXCEPTION 'submission team event mismatch';
  END IF;
  IF NEW.current_snapshot_id IS NOT NULL THEN
    SELECT submission_id INTO owning_submission FROM events_submissionsnapshot WHERE id=NEW.current_snapshot_id;
    IF owning_submission IS DISTINCT FROM NEW.id THEN
      RAISE EXCEPTION 'submission current snapshot mismatch';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def installation_sql():
    statements = [IMMUTABLE_FUNCTION, ASSET_FUNCTION, REFERENCE_FUNCTION, PROJECT_FUNCTION,
        "CREATE TRIGGER events_hackathonsubmission_owner BEFORE INSERT OR UPDATE ON events_hackathonsubmission "
        "FOR EACH ROW EXECUTE FUNCTION events_submission_project_guard();"]
    for table in IMMUTABLE_TABLES:
        statements.append(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                          "FOR EACH ROW EXECUTE FUNCTION events_submission_immutable();")
    for table in ("events_submissionasset", "events_hackathonparticipantasset"):
        statements.append(f"CREATE TRIGGER {table}_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} "
                          "FOR EACH ROW EXECUTE FUNCTION events_submission_asset_guard();")
    for table in IMMUTABLE_TABLES[1:]:
        statements.append(f"CREATE TRIGGER {table}_owner BEFORE INSERT ON {table} "
                          "FOR EACH ROW EXECUTE FUNCTION events_snapshot_reference_guard();")
    return tuple(statements)
