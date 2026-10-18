"""Private project documents and deployment-owned asset cleanup obligations."""
from django.db import migrations, models
import django.utils.timezone

REFERENCE_SQL = r"""
CREATE OR REPLACE FUNCTION events_snapshot_reference_guard() RETURNS trigger AS $$
DECLARE owning_submission bigint; owning_event bigint; owning_team bigint; valid boolean;
BEGIN
  SELECT s.id,s.event_id,s.team_id INTO owning_submission,owning_event,owning_team
    FROM events_submissionsnapshot snap JOIN events_hackathonsubmission s ON s.id=snap.submission_id
    WHERE snap.id=NEW.snapshot_id;
  IF TG_TABLE_NAME='events_snapshotasset' THEN
    SELECT (a.submission_id=owning_submission AND a.event_id=owning_event AND a.team_id=owning_team
      AND ((a.state='ready' AND a.scan_status IN ('clean','skipped') AND a.expired_at IS NULL
        AND (a.expires_at IS NULL OR a.expires_at>CURRENT_TIMESTAMP)) __HISTORICAL__)) INTO valid
      FROM events_submissionasset a JOIN events_event e ON e.id=a.event_id
      JOIN makerspaces_makerspace m ON m.id=e.makerspace_id WHERE a.id=NEW.asset_id;
  ELSIF TG_TABLE_NAME='events_snapshotlink' THEN
    SELECT submission_id=owning_submission INTO valid FROM events_submissionlink WHERE id=NEW.link_id;
  ELSIF TG_TABLE_NAME='events_snapshottrack' THEN
    SELECT event_id=owning_event INTO valid FROM events_hackathontrack WHERE id=NEW.track_id;
  ELSIF TG_TABLE_NAME='events_snapshotprize' THEN
    SELECT event_id=owning_event INTO valid FROM events_hackathonprize WHERE id=NEW.prize_id;
  END IF;
  IF valid IS DISTINCT FROM TRUE THEN RAISE EXCEPTION 'snapshot reference owner mismatch'; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
"""


SQL = r"""
CREATE FUNCTION events_project_pii_fence() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint;
BEGIN
  IF TG_TABLE_NAME='events_hackathonsubmission' THEN
    SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id;
  ELSIF TG_TABLE_NAME='events_submissionintegrityflag' THEN
    SELECT e.makerspace_id INTO host FROM events_event e
      JOIN events_hackathonsubmission s ON s.event_id=e.id
      JOIN events_submissionsnapshot snap ON snap.submission_id=s.id WHERE snap.id=NEW.snapshot_id;
  ELSE
    SELECT e.makerspace_id INTO host FROM events_event e
      JOIN events_hackathonsubmission s ON s.event_id=e.id WHERE s.id=NEW.submission_id;
  END IF;
  PERFORM pii_assert_mapped_write_allowed(host);
  RETURN NEW;
END; $$;
CREATE TRIGGER events_project_document_fence BEFORE INSERT OR UPDATE OF form_answers,triage_reason
  ON events_hackathonsubmission FOR EACH ROW EXECUTE FUNCTION events_project_pii_fence();
CREATE TRIGGER events_snapshot_document_fence BEFORE INSERT OR UPDATE OF project,amendment_reason
  ON events_submissionsnapshot FOR EACH ROW EXECUTE FUNCTION events_project_pii_fence();
CREATE TRIGGER events_integrity_reason_fence BEFORE INSERT OR UPDATE OF reason
  ON events_submissionintegrityflag FOR EACH ROW EXECUTE FUNCTION events_project_pii_fence();

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

CREATE FUNCTION events_asset_obligation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE asset_exists boolean; owned_key text;
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'asset obligations are permanent'; END IF;
  IF TG_OP='UPDATE' THEN
    IF (NEW.asset_uuid,NEW.asset_label,NEW.asset_id_snapshot,NEW.event_id_snapshot,NEW.makerspace_id_snapshot,
        NEW.object_key,NEW.staging_key,NEW.verification_key,NEW.managed)
      IS DISTINCT FROM
       (OLD.asset_uuid,OLD.asset_label,OLD.asset_id_snapshot,OLD.event_id_snapshot,OLD.makerspace_id_snapshot,
        OLD.object_key,OLD.staging_key,OLD.verification_key,OLD.managed) THEN
      RAISE EXCEPTION 'asset obligation custody is immutable';
    END IF;
    IF OLD.write_not_after IS NOT NULL AND (NEW.write_not_after IS NULL OR NEW.write_not_after<OLD.write_not_after) THEN
      RAISE EXCEPTION 'asset write deadline cannot move backwards';
    END IF;
    IF OLD.fully_released AND (NOT NEW.fully_released OR NEW.reserved_bytes<>0 OR NEW.charged_bytes<>0) THEN
      RAISE EXCEPTION 'released asset accounting cannot revive';
    END IF;
    IF (OLD.initial_bytes<>0 AND NEW.initial_bytes<>OLD.initial_bytes)
      OR (OLD.canonical_extra_bytes<>0 AND NEW.canonical_extra_bytes<>OLD.canonical_extra_bytes)
      OR (OLD.temporary_released AND NOT NEW.temporary_released)
      OR NEW.reserved_bytes+NEW.charged_bytes>NEW.initial_bytes+NEW.canonical_extra_bytes THEN
      RAISE EXCEPTION 'asset accounting receipt conflict';
    END IF;
    RETURN NEW;
  END IF;
  FOR owned_key IN SELECT k FROM unnest(ARRAY[NEW.object_key,NEW.staging_key,NEW.verification_key]) k ORDER BY k LOOP
    PERFORM pg_advisory_xact_lock(hashtextextended(owned_key,734318));
    IF EXISTS(SELECT 1 FROM events_eventassetobligation r
      WHERE owned_key IN (r.object_key,r.staging_key,r.verification_key)) THEN
      RAISE EXCEPTION 'asset locator is permanently reserved';
    END IF;
  END LOOP;
  IF NEW.asset_label='events.SubmissionAsset' THEN
    SELECT EXISTS(SELECT 1 FROM events_submissionasset a JOIN events_event e ON e.id=a.event_id
      WHERE a.id=NEW.asset_id_snapshot AND a.public_id=NEW.asset_uuid AND a.event_id=NEW.event_id_snapshot
      AND e.makerspace_id=NEW.makerspace_id_snapshot AND a.object_key=NEW.object_key
      AND a.staging_key=NEW.staging_key AND a.verification_key=NEW.verification_key) INTO asset_exists;
  ELSIF NEW.asset_label='events.HackathonParticipantAsset' THEN
    SELECT EXISTS(SELECT 1 FROM events_hackathonparticipantasset a JOIN events_event e ON e.id=a.event_id
      WHERE a.id=NEW.asset_id_snapshot AND a.public_id=NEW.asset_uuid AND a.event_id=NEW.event_id_snapshot
      AND e.makerspace_id=NEW.makerspace_id_snapshot AND a.object_key=NEW.object_key
      AND a.staging_key=NEW.staging_key AND a.verification_key=NEW.verification_key) INTO asset_exists;
  END IF;
  IF asset_exists IS DISTINCT FROM TRUE THEN RAISE EXCEPTION 'asset obligation owner mismatch'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER events_asset_obligation_custody BEFORE INSERT OR UPDATE OR DELETE ON events_eventassetobligation
  FOR EACH ROW EXECUTE FUNCTION events_asset_obligation_guard();

CREATE FUNCTION events_asset_locator_reserved() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owned_key text;
BEGIN
  IF TG_OP='UPDATE' AND (NEW.object_key,NEW.staging_key,NEW.verification_key,NEW.public_id)
    IS DISTINCT FROM (OLD.object_key,OLD.staging_key,OLD.verification_key,OLD.public_id) THEN
    RAISE EXCEPTION 'asset locators are immutable';
  END IF;
  IF TG_OP='INSERT' AND EXISTS(SELECT 1 FROM events_eventassetobligation WHERE asset_uuid=NEW.public_id) THEN
    RAISE EXCEPTION 'asset identity is permanently reserved';
  END IF;
  FOR owned_key IN SELECT k FROM unnest(ARRAY[NEW.object_key,NEW.staging_key,NEW.verification_key]) k ORDER BY k LOOP
    PERFORM pg_advisory_xact_lock(hashtextextended(owned_key,734318));
    IF EXISTS(SELECT 1 FROM events_eventassetobligation r
      WHERE owned_key IN (r.object_key,r.staging_key,r.verification_key)
      AND (r.asset_uuid<>NEW.public_id OR r.asset_id_snapshot<>NEW.id
        OR lower(replace(r.asset_label,'events.','events_'))<>TG_TABLE_NAME
        OR (r.object_key,r.staging_key,r.verification_key)
          IS DISTINCT FROM (NEW.object_key,NEW.staging_key,NEW.verification_key))) THEN
      RAISE EXCEPTION 'asset locator is permanently reserved';
    END IF;
  END LOOP;
  RETURN NEW;
END; $$;
CREATE TRIGGER events_submission_locator_reserved BEFORE INSERT OR UPDATE OF object_key,staging_key,verification_key,public_id
  ON events_submissionasset FOR EACH ROW EXECUTE FUNCTION events_asset_locator_reserved();
CREATE TRIGGER events_participant_locator_reserved BEFORE INSERT OR UPDATE OF object_key,staging_key,verification_key,public_id
  ON events_hackathonparticipantasset FOR EACH ROW EXECUTE FUNCTION events_asset_locator_reserved();
"""
SQL += REFERENCE_SQL.replace("__HISTORICAL__", "OR (m.lifecycle_state='importing' AND a.state='expired' AND a.expired_at IS NOT NULL)")

REVERSE = r"""
DO $$ BEGIN
  IF EXISTS(SELECT 1 FROM events_eventassetobligation) THEN
    RAISE EXCEPTION 'Permanent asset obligations prevent downgrade';
  END IF;
  IF EXISTS(SELECT 1 FROM events_hackathonsubmission WHERE form_answers LIKE 'pii:gcm:v1:%')
    OR EXISTS(SELECT 1 FROM events_submissionsnapshot WHERE project LIKE 'pii:gcm:v1:%' OR amendment_reason LIKE 'pii:gcm:v1:%')
    OR EXISTS(SELECT 1 FROM events_hackathonsubmission WHERE triage_reason LIKE 'pii:gcm:v1:%')
    OR EXISTS(SELECT 1 FROM events_submissionintegrityflag WHERE reason LIKE 'pii:gcm:v1:%') THEN
    RAISE EXCEPTION 'Decrypt private documents before downgrade';
  END IF;
END $$;
DROP TRIGGER events_participant_locator_reserved ON events_hackathonparticipantasset;
DROP TRIGGER events_submission_locator_reserved ON events_submissionasset;
DROP FUNCTION events_asset_locator_reserved();
DROP TRIGGER events_asset_obligation_custody ON events_eventassetobligation;
DROP FUNCTION events_asset_obligation_guard();
DROP TRIGGER events_snapshot_document_fence ON events_submissionsnapshot;
DROP TRIGGER events_integrity_reason_fence ON events_submissionintegrityflag;
DROP TRIGGER events_project_document_fence ON events_hackathonsubmission;
DROP FUNCTION events_project_pii_fence();
CREATE OR REPLACE FUNCTION events_submission_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'submission snapshot is immutable';
END; $$ LANGUAGE plpgsql;
"""
REVERSE += REFERENCE_SQL.replace("__HISTORICAL__", "")


def custody_existing(apps, schema_editor):
    from django.conf import settings
    receipt = apps.get_model("events", "EventAssetObligation")
    managed = bool(str(settings.PLATFORM_DOMAIN_SUFFIX or "").strip())
    totals = {}
    for label in ("SubmissionAsset", "HackathonParticipantAsset"):
        model = apps.get_model("events", label)
        for asset in model.objects.select_related("event").iterator(chunk_size=200):
            receipt.objects.create(asset_uuid=asset.public_id, asset_label=f"events.{label}",
                asset_id_snapshot=asset.pk, event_id_snapshot=asset.event_id,
                makerspace_id_snapshot=asset.event.makerspace_id, object_key=asset.object_key,
                staging_key=asset.staging_key, verification_key=asset.verification_key,
                multipart_upload_id=asset.multipart_upload_id, initial_bytes=asset.declared_bytes,
                reserved_bytes=asset.reserved_bytes, charged_bytes=asset.charged_bytes,
                canonical_extra_bytes=max(0,asset.reserved_bytes+asset.charged_bytes-asset.declared_bytes),
                temporary_released=not asset.reserved_bytes, fully_released=bool(asset.deleted_at),
                write_not_after=asset.upload_not_after, managed=managed)
            totals[asset.event.makerspace_id] = totals.get(asset.event.makerspace_id, 0) + asset.reserved_bytes + asset.charged_bytes
    if managed:
        # GF1 had no installed provider callback. Backfill its previously
        # unaccounted event pool once, without applying the ordinary base cap.
        space = apps.get_model("makerspaces", "Makerspace")
        for pk, size in totals.items():
            space.objects.filter(pk=pk).update(storage_bytes_used=models.F("storage_bytes_used")+size)


class Migration(migrations.Migration):
    dependencies = [("events", "0040_g2b_subject_lifecycle")]
    operations = [
        migrations.AlterField("hackathonsubmission", "form_answers", models.TextField(default="{}")),
        migrations.AlterField("submissionsnapshot", "project", models.TextField()),
        migrations.AlterField("hackathonsubmission", "triage_reason", models.TextField(max_length=1000, blank=True)),
        migrations.AlterField("submissionsnapshot", "amendment_reason", models.TextField(max_length=1000, blank=True)),
        migrations.AlterField("submissionintegrityflag", "reason", models.TextField(max_length=1000, blank=True)),
        migrations.CreateModel(name="EventProgrammeSweepCursor", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("namespace", models.CharField(max_length=64, unique=True)),
            ("last_id", models.PositiveBigIntegerField(default=0)),
        ]),
        migrations.CreateModel(name="EventAssetObligation", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("asset_uuid", models.UUIDField(unique=True)),
            ("asset_label", models.CharField(max_length=64)),
            ("asset_id_snapshot", models.PositiveBigIntegerField()),
            ("event_id_snapshot", models.PositiveBigIntegerField()),
            ("makerspace_id_snapshot", models.PositiveBigIntegerField()),
            ("object_key", models.CharField(max_length=512, unique=True)),
            ("staging_key", models.CharField(max_length=512, unique=True)),
            ("verification_key", models.CharField(max_length=512, unique=True)),
            ("multipart_upload_id", models.TextField(blank=True)),
            ("initial_bytes", models.PositiveBigIntegerField(default=0)),
            ("canonical_extra_bytes", models.PositiveBigIntegerField(default=0)),
            ("reserved_bytes", models.PositiveBigIntegerField(default=0)),
            ("charged_bytes", models.PositiveBigIntegerField(default=0)),
            ("temporary_released", models.BooleanField(default=False)),
            ("fully_released", models.BooleanField(default=False)),
            ("managed", models.BooleanField(default=False)),
            ("write_not_after", models.DateTimeField(null=True)),
            ("next_attempt_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ("lease_token", models.UUIDField(null=True)),
            ("lease_until", models.DateTimeField(null=True)),
            ("attempts", models.PositiveIntegerField(default=0)),
            ("last_code", models.CharField(blank=True, max_length=64)),
            ("last_cleaned_at", models.DateTimeField(null=True)),
        ]),
        migrations.RunPython(custody_existing, migrations.RunPython.noop),
        migrations.RunSQL(SQL, REVERSE),
    ]
