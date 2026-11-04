"""Two 0039 guard corrections.

* A cohort decision has no application row: scope the notified pointer by its batch
  event. 0039 resolved it through ``application_id`` only, so releasing a team/cohort
  decision (application NULL, cohort set) raised "event mismatch" for every member.
* Import publication records the target bucket's version id on a ready asset once
  (empty -> value); 0039 froze ``final_version_id`` with the content columns, so every
  imported ready asset failed to finalize. A recorded version id stays immutable.
"""
from django.db import migrations


def _function(decision_scope):
    return f"""
CREATE OR REPLACE FUNCTION events_hackathonapplication_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.registration_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme registration event mismatch'; END IF;
  IF NEW.cohort_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplicationcohort r WHERE r.id=NEW.cohort_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme cohort event mismatch'; END IF;
  IF NEW.notified_decision_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_applicationdecision r WHERE r.id=NEW.notified_decision_id AND {decision_scope}=owner_event) THEN RAISE EXCEPTION 'programme notified_decision event mismatch'; END IF;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
"""


ASSET_GUARD = """
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
  IF TG_OP = 'UPDATE' AND (OLD.ready_at IS NOT NULL OR OLD.sha256 <> '') AND (
    (NEW.sha256, NEW.original_sha256, NEW.actual_bytes, NEW.canonical_mime, NEW.object_key,
     NEW.event_id, NEW.public_id, NEW.generation)
    IS DISTINCT FROM
    (OLD.sha256, OLD.original_sha256, OLD.actual_bytes, OLD.canonical_mime, OLD.object_key,
     OLD.event_id, OLD.public_id, OLD.generation)
    -- The target bucket's version id may be recorded once, by import publication.
    OR (OLD.final_version_id <> '' AND NEW.final_version_id IS DISTINCT FROM OLD.final_version_id)) THEN
    RAISE EXCEPTION 'ready submission asset content is immutable';
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.expired_at IS NOT NULL AND NEW.expired_at IS NULL THEN
    RAISE EXCEPTION 'expired submission asset cannot revive';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
ASSET_GUARD_0039 = """
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

FORWARD = _function("(SELECT b.event_id FROM events_applicationdecisionbatch b WHERE b.id=r.batch_id)") + ASSET_GUARD
REVERSE = _function("(SELECT p2.event_id FROM events_hackathonapplication p2 WHERE p2.id=r.application_id)") + ASSET_GUARD_0039


class Migration(migrations.Migration):
    dependencies = [("events", "0052_programme_field_state")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
