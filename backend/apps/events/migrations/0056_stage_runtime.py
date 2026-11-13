"""Stage-form runtime rows, frozen assignment policy and corrected history guards.

Adds the activation/reconcile work rows and FK-free StageFileCleanup locators, freezes
each existing assignment's policy and event-date revision from its definition, seeds
one permanent cleanup locator per existing stage asset, and replaces two 0049 guard
bodies: a response's historical submitted-revision pointer survives a reassigned
replacement draft, and an attached asset stays maintainable after its assignment is
re-pinned (binding is checked on INSERT and immutable afterwards).
"""
import importlib
from datetime import timedelta

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

_G = importlib.import_module("apps.events.migrations.0054_reimbursement_guards")
_TABLES = [rule[0] for rule in _G.RULES]

POLICY_FIELDS = (
    "stage", "activation_point", "required", "missed_action", "blocked_actions", "lock_on_next_stage",
    "audience", "opening_mode", "opening_offset_seconds", "due_mode", "due_after_seconds",
    "due_event_offset_seconds", "reminder_offsets",
)

OLD_RESPONSE_POINTER = (
    "r.response_id=NEW.id AND r.form_revision_id=NEW.form_revision_id) "
    "THEN RAISE EXCEPTION 'stage submitted revision mismatch'"
)
NEW_RESPONSE_POINTER = "r.response_id=NEW.id) THEN RAISE EXCEPTION 'stage submitted revision mismatch'"

OLD_ASSET_PIN = (
    "IF NOT EXISTS (SELECT 1 FROM events_stageformassignment a WHERE a.id=NEW.assignment_id "
    "AND a.owner_member_id=NEW.owner_member_id AND a.pinned_form_revision_id=NEW.form_revision_id) "
    "THEN RAISE EXCEPTION 'stage asset assignment mismatch'; END IF;"
)
NEW_ASSET_PIN = (
    "IF TG_OP='INSERT' AND NOT EXISTS (SELECT 1 FROM events_stageformassignment a WHERE a.id=NEW.assignment_id "
    "AND a.owner_member_id=NEW.owner_member_id AND a.pinned_form_revision_id=NEW.form_revision_id) "
    "THEN RAISE EXCEPTION 'stage asset assignment mismatch'; END IF; "
    "IF TG_OP='UPDATE' AND (NEW.assignment_id, NEW.owner_member_id, NEW.form_revision_id, NEW.event_id) "
    "IS DISTINCT FROM (OLD.assignment_id, OLD.owner_member_id, OLD.form_revision_id, OLD.event_id) "
    "THEN RAISE EXCEPTION 'stage asset binding is immutable'; END IF; "
    "IF NOT EXISTS (SELECT 1 FROM events_stageformassignment a JOIN events_eventformrevision f "
    "ON f.id=NEW.form_revision_id WHERE a.id=NEW.assignment_id AND a.owner_member_id=NEW.owner_member_id "
    "AND f.form_key='stage' AND f.selector_kind='stage' AND f.selector_id=a.stage_form_id) "
    "THEN RAISE EXCEPTION 'stage asset assignment mismatch'; END IF;"
)

OLD_ASSIGNMENT_COMPLETED = (
    "AND r.assignment_id=NEW.id AND r.owner_member_id=NEW.owner_member_id) "
    "THEN RAISE EXCEPTION 'stage completed response mismatch'; END IF;"
)
NEW_ASSIGNMENT_COMPLETED = (
    "AND r.assignment_id=NEW.id AND r.owner_member_id=NEW.owner_member_id "
    "AND r.form_revision_id=NEW.pinned_form_revision_id) "
    "THEN RAISE EXCEPTION 'stage completed response mismatch'; END IF;"
)

REPLACEMENTS = {
    "events_stageformassignment": (OLD_ASSIGNMENT_COMPLETED, NEW_ASSIGNMENT_COMPLETED),
    "events_stageformresponse": (OLD_RESPONSE_POINTER, NEW_RESPONSE_POINTER),
    "events_stageformasset": (OLD_ASSET_PIN, NEW_ASSET_PIN),
}


def _function_body(table):
    """0049's exact CREATE FUNCTION text for one table, as CREATE OR REPLACE."""
    text = _G.FORWARD[_TABLES.index(table)]
    body = text[:text.index("CREATE TRIGGER")]
    return body.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)


def _replaced(table):
    old, new = REPLACEMENTS[table]
    body = _function_body(table)
    if body.count(old) != 1:
        raise RuntimeError(f"0049 guard for {table} no longer matches the expected predicate")
    return body.replace(old, new)


GUARD_FORWARD = "\n".join(_replaced(table) for table in REPLACEMENTS)
GUARD_REVERSE = "\n".join(_function_body(table) for table in REPLACEMENTS)

CLEANUP_FORWARD = r"""
CREATE FUNCTION events_stage_file_cleanup_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'stage cleanup locators are permanent'; END IF;
  IF (NEW.source_asset_id,NEW.tenant_id,NEW.event_id_snapshot,NEW.bucket,NEW.staging_key,NEW.object_key)
    IS DISTINCT FROM (OLD.source_asset_id,OLD.tenant_id,OLD.event_id_snapshot,OLD.bucket,OLD.staging_key,OLD.object_key)
    THEN RAISE EXCEPTION 'stage cleanup locators are immutable'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER events_stage_file_cleanup_guard BEFORE UPDATE OR DELETE ON events_stagefilecleanup
  FOR EACH ROW EXECUTE FUNCTION events_stage_file_cleanup_guard();
"""
CLEANUP_REVERSE = r"""
DROP TRIGGER events_stage_file_cleanup_guard ON events_stagefilecleanup;
DROP FUNCTION events_stage_file_cleanup_guard();
"""


def freeze_assignment_policy(apps, schema_editor):
    Assignment = apps.get_model("events", "StageFormAssignment")
    rows = Assignment.objects.select_related("stage_form", "event").order_by("pk")
    for row in rows.iterator(chunk_size=200):
        definition = row.stage_form
        snapshot = {name: getattr(definition, name) for name in POLICY_FIELDS}
        snapshot["opens_at"] = definition.opens_at.isoformat() if definition.opens_at else None
        snapshot["due_at"] = definition.due_at.isoformat() if definition.due_at else None
        snapshot["lock_suppressed_through_rank"] = -1
        Assignment.objects.filter(pk=row.pk).update(
            policy_snapshot=snapshot, schedule_event_date_revision=row.event.event_date_revision)


def seed_cleanup_locators(apps, schema_editor):
    Asset = apps.get_model("events", "StageFormAsset")
    Cleanup = apps.get_model("events", "StageFileCleanup")
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    for asset in Asset.objects.select_related("event").order_by("pk").iterator(chunk_size=200):
        due = asset.expires_at or asset.created_at + timedelta(hours=24)
        Cleanup.objects.get_or_create(source_asset_id=asset.pk, defaults={
            "tenant_id": asset.event.makerspace_id, "event_id_snapshot": asset.event_id, "bucket": bucket,
            "staging_key": asset.staging_key, "object_key": asset.object_key,
            "not_before": due, "next_attempt_at": due,
        })


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0055_stage_selector_ownership"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StageActivationJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation_id", models.UUIDField(unique=True)),
                ("command_digest", models.CharField(max_length=64)),
                ("participant_ids", models.JSONField()),
                ("effective_due_at", models.DateTimeField()),
                ("state", models.CharField(choices=[("pending", "pending"), ("completed", "completed"), ("cancelled", "cancelled")], default="pending", max_length=12)),
                ("cursor", models.PositiveIntegerField(default=0)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stage_activation_jobs", to="events.event")),
                ("pinned_form_revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="events.eventformrevision")),
                ("stage_form", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activation_jobs", to="events.eventstageform")),
            ],
        ),
        migrations.CreateModel(
            name="StageFileCleanup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_asset_id", models.PositiveBigIntegerField(unique=True)),
                ("tenant_id", models.PositiveBigIntegerField(db_index=True)),
                ("event_id_snapshot", models.PositiveBigIntegerField()),
                ("bucket", models.CharField(max_length=255)),
                ("staging_key", models.CharField(max_length=500, unique=True)),
                ("object_key", models.CharField(max_length=500, unique=True)),
                ("not_before", models.DateTimeField()),
                ("next_attempt_at", models.DateTimeField(db_index=True)),
                ("lease_token", models.UUIDField(null=True)),
                ("lease_until", models.DateTimeField(null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_deleted_at", models.DateTimeField(null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=64)),
            ],
        ),
        migrations.CreateModel(
            name="StageReconcileCursor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_owner_id", models.PositiveBigIntegerField(default=0)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("event", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="stage_reconcile_cursor", to="events.event")),
            ],
        ),
        migrations.AddField(
            model_name="stageformassignment",
            name="policy_snapshot",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="stageformassignment",
            name="schedule_event_date_revision",
            field=models.PositiveBigIntegerField(default=1),
        ),
        migrations.RunPython(freeze_assignment_policy, migrations.RunPython.noop),
        migrations.RunPython(seed_cleanup_locators, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="stageformasset",
            constraint=models.CheckConstraint(condition=models.Q(("generation__gte", 1), ("version__gte", 1)), name="stage_asset_versions"),
        ),
        migrations.AddConstraint(
            model_name="stageformasset",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("state__in", ("ready", "attached")), _negated=True), models.Q(("actual_bytes", models.F("expected_bytes")), ("actual_bytes__isnull", False), ("canonical_mime__in", ("application/pdf", "image/jpeg", "image/png", "image/heic")), ("scan_status__in", ("clean", "skipped")), ("sha256__regex", "^[a-f0-9]{64}$")), _connector="OR"), name="stage_asset_ready_integrity"),
        ),
        migrations.RunSQL(CLEANUP_FORWARD, CLEANUP_REVERSE),
        migrations.RunSQL(GUARD_FORWARD, GUARD_REVERSE),
    ]
