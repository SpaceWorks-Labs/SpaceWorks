"""Fenced representation changes preserve every immutable programme value outside PII."""
from django.db import migrations

SQL = r"""
CREATE FUNCTION events_programme_pii_maintenance(before_row jsonb, after_row jsonb, host bigint, columns text[])
RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE operation text; kind text; field_name text;
BEGIN
  IF host IS NULL OR (before_row-columns) IS DISTINCT FROM (after_row-columns) THEN RETURN FALSE; END IF;
  operation := current_setting('app.pii_fence_operation',true);
  IF operation IS NULL OR operation='' THEN RETURN FALSE; END IF;
  PERFORM pii_assert_mapped_write_allowed(host);
  SELECT g.operation_kind INTO kind FROM encryption_piiglobalwritefence g
    JOIN encryption_piimakerspacewritefence t ON t.makerspace_id=host
    WHERE g.id=1 AND g.state='closed' AND t.state='closed'
      AND g.operation_id::text=operation AND t.operation_id::text=operation
      AND g.operation_kind=t.operation_kind
      AND g.operation_kind IN ('enable_transition','decrypt_rollback');
  IF kind IS NULL THEN RETURN FALSE; END IF;
  FOREACH field_name IN ARRAY columns LOOP
    IF (before_row->field_name) IS DISTINCT FROM (after_row->field_name) THEN
      IF kind='enable_transition' AND COALESCE(after_row->>field_name,'') NOT LIKE 'pii:gcm:v1:%' THEN RETURN FALSE; END IF;
      IF kind='decrypt_rollback' AND (COALESCE(before_row->>field_name,'') NOT LIKE 'pii:gcm:v1:%'
          OR COALESCE(after_row->>field_name,'') LIKE 'pii:gcm:v1:%') THEN RETURN FALSE; END IF;
    END IF;
  END LOOP;
  RETURN TRUE;
END; $$;

CREATE OR REPLACE FUNCTION events_hackathonapplicationanswerrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      (SELECT e.makerspace_id FROM events_hackathonapplication a JOIN events_event e ON e.id=a.event_id WHERE a.id=OLD.application_id),ARRAY['answers_snapshot','profile_snapshot']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_applicationreview_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      (SELECT e.makerspace_id FROM events_applicationreviewassignment a JOIN events_event e ON e.id=a.event_id WHERE a.id=OLD.assignment_id),ARRAY['notes']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_teamcomment_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      (SELECT e.makerspace_id FROM events_hackathonteam t JOIN events_event e ON e.id=t.event_id WHERE t.id=OLD.team_id),ARRAY['encrypted_body']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventcontributionhoursentry_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['reason']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventshiftattendancecorrection_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['reason']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventhelpaction_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['note']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventhelpcomment_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['body']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.author_id IS NOT DISTINCT FROM OLD.author_id OR (NEW.author_id IS NULL AND OLD.author_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['author_id']::text[])=(to_jsonb(OLD)-ARRAY['author_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_mentorroundcheckin_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['answers','overrides']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_officehourschange_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['reason']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventroleanswerrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['answers','reason']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventrequirementoverride_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['reason']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_judgingreason_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['body']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_programme_score_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE configuration jsonb; mode text;
BEGIN
  IF TG_OP='UPDATE' AND events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      OLD.makerspace_id,ARRAY['notes']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' THEN
    IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'judgment evidence is retained';
  END IF;
  IF TG_OP='UPDATE' AND OLD.submitted_at IS NOT NULL THEN RAISE EXCEPTION 'submitted judgment is immutable'; END IF;
  SELECT r.configuration,r.mode INTO configuration,mode FROM events_judgeassignment a
    JOIN events_judginground r ON r.id=a.round_id WHERE a.id=NEW.assignment_id;
  IF jsonb_typeof(NEW.criterion_values)<>'object' THEN RAISE EXCEPTION 'invalid score shape'; END IF;
  IF NEW.submitted_at IS NOT NULL THEN
    IF mode IS DISTINCT FROM 'weighted_1_5' OR jsonb_typeof(configuration->'criteria') IS DISTINCT FROM 'array'
      THEN RAISE EXCEPTION 'submitted score requires frozen weighted rubric'; END IF;
    IF EXISTS (SELECT 1 FROM jsonb_each(NEW.criterion_values) v
      WHERE jsonb_typeof(v.value)<>'number' OR v.value::text !~ '^[1-5]$')
      OR EXISTS (SELECT jsonb_object_keys(NEW.criterion_values) EXCEPT SELECT c->>'key' FROM jsonb_array_elements(configuration->'criteria') c)
      OR EXISTS (SELECT c->>'key' FROM jsonb_array_elements(configuration->'criteria') c EXCEPT SELECT jsonb_object_keys(NEW.criterion_values))
      THEN RAISE EXCEPTION 'submitted scores require every frozen key and integer 1..5'; END IF;
  END IF;
  RETURN NEW;
END;
$$;
CREATE OR REPLACE FUNCTION events_submission_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND TG_TABLE_NAME='events_submissionsnapshot' THEN
    IF events_programme_pii_maintenance(to_jsonb(OLD),to_jsonb(NEW),
      (SELECT e.makerspace_id FROM events_event e JOIN events_hackathonsubmission s ON s.event_id=e.id WHERE s.id=OLD.submission_id),
      ARRAY['project','amendment_reason']::text[]) THEN RETURN NEW; END IF;
  END IF;
  RAISE EXCEPTION 'submission snapshot is immutable';
END; $$ LANGUAGE plpgsql;
"""

REVERSE = r"""
CREATE OR REPLACE FUNCTION events_hackathonapplicationanswerrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_applicationreview_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_teamcomment_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventcontributionhoursentry_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventshiftattendancecorrection_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventhelpaction_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventhelpcomment_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.author_id IS NOT DISTINCT FROM OLD.author_id OR (NEW.author_id IS NULL AND OLD.author_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['author_id']::text[])=(to_jsonb(OLD)-ARRAY['author_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_mentorroundcheckin_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_officehourschange_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventroleanswerrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_eventrequirementoverride_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_judgingreason_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE OR REPLACE FUNCTION events_programme_score_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE configuration jsonb; mode text;
BEGIN
  IF TG_OP='DELETE' THEN
    IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'judgment evidence is retained';
  END IF;
  IF TG_OP='UPDATE' AND OLD.submitted_at IS NOT NULL THEN RAISE EXCEPTION 'submitted judgment is immutable'; END IF;
  SELECT r.configuration,r.mode INTO configuration,mode FROM events_judgeassignment a
    JOIN events_judginground r ON r.id=a.round_id WHERE a.id=NEW.assignment_id;
  IF jsonb_typeof(NEW.criterion_values)<>'object' THEN RAISE EXCEPTION 'invalid score shape'; END IF;
  IF NEW.submitted_at IS NOT NULL THEN
    IF mode IS DISTINCT FROM 'weighted_1_5' OR jsonb_typeof(configuration->'criteria') IS DISTINCT FROM 'array'
      THEN RAISE EXCEPTION 'submitted score requires frozen weighted rubric'; END IF;
    IF EXISTS (SELECT 1 FROM jsonb_each(NEW.criterion_values) v
      WHERE jsonb_typeof(v.value)<>'number' OR v.value::text !~ '^[1-5]$')
      OR EXISTS (SELECT jsonb_object_keys(NEW.criterion_values) EXCEPT SELECT c->>'key' FROM jsonb_array_elements(configuration->'criteria') c)
      OR EXISTS (SELECT c->>'key' FROM jsonb_array_elements(configuration->'criteria') c EXCEPT SELECT jsonb_object_keys(NEW.criterion_values))
      THEN RAISE EXCEPTION 'submitted scores require every frozen key and integer 1..5'; END IF;
  END IF;
  RETURN NEW;
END;
$$;
CREATE OR REPLACE FUNCTION events_submission_immutable() RETURNS trigger AS $$
DECLARE host bigint; operation text;
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND TG_TABLE_NAME='events_submissionsnapshot' THEN
    IF (to_jsonb(NEW)-'project'-'amendment_reason') IS NOT DISTINCT FROM (to_jsonb(OLD)-'project'-'amendment_reason') THEN
      SELECT e.makerspace_id INTO host FROM events_event e
        JOIN events_hackathonsubmission s ON s.event_id=e.id WHERE s.id=OLD.submission_id;
      PERFORM pii_assert_mapped_write_allowed(host);
      operation := current_setting('app.pii_fence_operation',true);
      IF EXISTS(SELECT 1 FROM encryption_piiglobalwritefence WHERE id=1 AND state='closed'
        AND operation_id::text=operation AND operation_kind IN ('enable_transition','decrypt_rollback'))
        OR EXISTS(SELECT 1 FROM encryption_piimakerspacewritefence WHERE makerspace_id=host AND state='closed'
        AND operation_id::text=operation AND operation_kind IN ('enable_transition','decrypt_rollback')) THEN
        RETURN NEW;
      END IF;
    END IF;
  END IF;
  RAISE EXCEPTION 'submission snapshot is immutable';
END; $$ LANGUAGE plpgsql;
DROP FUNCTION events_programme_pii_maintenance(jsonb,jsonb,bigint,text[]);
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0050_gf4_event_accent")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
