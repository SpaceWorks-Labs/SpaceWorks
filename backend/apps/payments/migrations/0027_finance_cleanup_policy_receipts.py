"""Finance cleanup locators, receipt retention policy and payout command receipts.

Creates the RB3-B core rows, seeds one permanent FK-free cleanup locator per existing
finance attachment BEFORE its delete guard exists, then installs the locator, policy
history and command-receipt guards. The attachment scope check now compares retained
event_id_snapshot values, so clearing a nullable Event FK during a real Events purge
works in either order, and verified attachment facts become immutable. The seven
ledger ``id`` AlterFields are state-only (0023 omitted serialize=False).
"""
import importlib
from uuid import uuid4

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

_G = importlib.import_module("apps.payments.migrations.0025_reimbursement_guards")
_TABLES = [rule[0] for rule in _G.RULES]


def _previous_attachment_guard():
    text = _G.FORWARD[_TABLES.index("payments_financeattachment")]
    body = text[:text.index("CREATE TRIGGER")]
    return body.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)


GUARD_SQL = r"""
CREATE FUNCTION finance_cleanup_locator_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'finance cleanup locators are permanent'; END IF;
  IF (NEW.source_makerspace_id,NEW.asset_id,NEW.bucket,NEW.staging_key,NEW.object_key)
    IS DISTINCT FROM (OLD.source_makerspace_id,OLD.asset_id,OLD.bucket,OLD.staging_key,OLD.object_key)
    THEN RAISE EXCEPTION 'finance cleanup locators are immutable'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER finance_cleanup_locator_guard BEFORE UPDATE OR DELETE ON payments_financeobjectcleanup
FOR EACH ROW EXECUTE FUNCTION finance_cleanup_locator_guard();

CREATE FUNCTION finance_policy_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP IN ('UPDATE','DELETE') THEN RAISE EXCEPTION 'finance policy history is immutable'; END IF;
  PERFORM pii_assert_mapped_write_allowed(NEW.makerspace_id);
  IF NEW.receipt_days<1 OR NEW.receipt_days>36500 OR NEW.policy_version<1
    THEN RAISE EXCEPTION 'invalid finance retention policy'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER finance_policy_revision_guard BEFORE INSERT OR UPDATE OR DELETE ON payments_financeretentionpolicyrevision
FOR EACH ROW EXECUTE FUNCTION finance_policy_revision_guard();

CREATE FUNCTION finance_command_receipt_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pii_assert_mapped_write_allowed(NEW.makerspace_id);
  IF NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation o WHERE o.id=NEW.obligation_id AND o.makerspace_id=NEW.makerspace_id)
    THEN RAISE EXCEPTION 'finance command receipt scope mismatch'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER finance_command_receipt_guard BEFORE INSERT OR UPDATE ON payments_eventpayoutcommandreceipt
FOR EACH ROW EXECUTE FUNCTION finance_command_receipt_guard();
"""

REVERSE_GUARD_SQL = r"""
DROP TRIGGER finance_command_receipt_guard ON payments_eventpayoutcommandreceipt;
DROP FUNCTION finance_command_receipt_guard();
DROP TRIGGER finance_policy_revision_guard ON payments_financeretentionpolicyrevision;
DROP FUNCTION finance_policy_revision_guard();
DROP TRIGGER finance_cleanup_locator_guard ON payments_financeobjectcleanup;
DROP FUNCTION finance_cleanup_locator_guard();
"""

ATTACHMENT_SCOPE_SQL = r"""
CREATE OR REPLACE FUNCTION payments_financeattachment_rg_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tenant_id bigint;
BEGIN
  tenant_id := NEW.makerspace_id;
  IF tenant_id IS NULL THEN RAISE EXCEPTION 'reimbursement host missing'; END IF;
  PERFORM pii_assert_mapped_write_allowed(tenant_id);
  IF NEW.event_id IS NOT NULL AND NOT EXISTS
    (SELECT 1 FROM events_event e WHERE e.id=NEW.event_id AND e.makerspace_id=tenant_id AND e.id=NEW.event_id_snapshot)
    THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;
  IF NEW.owner_member_id IS NOT NULL AND NOT EXISTS
    (SELECT 1 FROM accounts_user u WHERE u.id=NEW.owner_member_id AND u.account_kind='member')
    THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;
  IF NEW.obligation_id IS NOT NULL AND NOT EXISTS
    (SELECT 1 FROM payments_eventpayoutobligation o WHERE o.id=NEW.obligation_id
      AND o.makerspace_id=tenant_id AND o.event_id_snapshot=NEW.event_id_snapshot
      AND (NEW.owner_member_id IS NULL OR o.owner_member_id IS NULL OR o.owner_member_id=NEW.owner_member_id))
    THEN RAISE EXCEPTION 'attachment obligation scope mismatch'; END IF;
  RETURN NEW;
END; $$;
"""

ATTACHMENT_FACTS_SQL = r"""
CREATE FUNCTION finance_attachment_facts_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.makerspace_id,NEW.event_id_snapshot,NEW.event_title_snapshot,NEW.purpose,NEW.binding_kind,
      NEW.binding_uuid,NEW.question_id,NEW.generation,NEW.expected_bytes,NEW.declared_mime,
      NEW.staging_key,NEW.object_key,NEW.retention_policy_revision,NEW.retention_days_snapshot)
     IS DISTINCT FROM
     (OLD.makerspace_id,OLD.event_id_snapshot,OLD.event_title_snapshot,OLD.purpose,OLD.binding_kind,
      OLD.binding_uuid,OLD.question_id,OLD.generation,OLD.expected_bytes,OLD.declared_mime,
      OLD.staging_key,OLD.object_key,OLD.retention_policy_revision,OLD.retention_days_snapshot)
    THEN RAISE EXCEPTION 'finance attachment binding is immutable'; END IF;
  IF OLD.sha256<>'' AND (NEW.actual_bytes,NEW.canonical_mime,NEW.sha256,NEW.final_version_id,NEW.staging_version_id)
    IS DISTINCT FROM (OLD.actual_bytes,OLD.canonical_mime,OLD.sha256,OLD.final_version_id,OLD.staging_version_id)
    THEN RAISE EXCEPTION 'verified finance attachment facts are immutable'; END IF;
  IF OLD.obligation_id IS NOT NULL AND NEW.obligation_id IS DISTINCT FROM OLD.obligation_id
    THEN RAISE EXCEPTION 'finance attachment obligation is immutable'; END IF;
  IF NEW.owner_member_id IS DISTINCT FROM OLD.owner_member_id AND NEW.owner_member_id IS NOT NULL
    THEN RAISE EXCEPTION 'finance attachment owner cannot be reassigned'; END IF;
  IF OLD.state IN ('expired','deleting','deleted') AND NEW.state NOT IN ('expired','deleting','deleted')
    THEN RAISE EXCEPTION 'expired finance attachment cannot be restored'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER finance_attachment_facts_guard BEFORE UPDATE ON payments_financeattachment
FOR EACH ROW EXECUTE FUNCTION finance_attachment_facts_guard();
"""

REVERSE_ATTACHMENT_FACTS_SQL = r"""
DROP TRIGGER finance_attachment_facts_guard ON payments_financeattachment;
DROP FUNCTION finance_attachment_facts_guard();
"""


def backfill_cleanup_locators(apps, schema_editor):
    from django.utils import timezone
    Attachment = apps.get_model("payments", "FinanceAttachment")
    Cleanup = apps.get_model("payments", "FinanceObjectCleanup")
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    for row in Attachment.objects.order_by("pk").iterator(chunk_size=100):
        Cleanup.objects.get_or_create(asset_id=row.pk, defaults={
            "source_makerspace_id": row.makerspace_id, "bucket": bucket,
            "staging_key": row.staging_key, "object_key": row.object_key,
            "next_attempt_at": timezone.now() if row.state in ("expired", "deleting", "deleted") else None,
        })


def _uuid_pk(model_name):
    return migrations.AlterField(model_name=model_name, name="id",
                                 field=models.UUIDField(default=uuid4, editable=False, primary_key=True, serialize=False))


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0026_reimbursement_ledger_integrity"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FinanceObjectCleanup",
            fields=[
                ("id", models.UUIDField(default=uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_makerspace_id", models.PositiveBigIntegerField()),
                ("asset_id", models.PositiveBigIntegerField(unique=True)),
                ("bucket", models.CharField(max_length=200)),
                ("staging_key", models.CharField(max_length=500, unique=True)),
                ("object_key", models.CharField(max_length=500, unique=True)),
                ("next_attempt_at", models.DateTimeField(db_index=True, null=True)),
                ("lease_token", models.UUIDField(null=True)),
                ("lease_until", models.DateTimeField(null=True)),
                ("attempts", models.PositiveBigIntegerField(default=0)),
                ("deleted_at", models.DateTimeField(null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="FinanceSweepCursor",
            fields=[
                ("key", models.CharField(max_length=32, primary_key=True, serialize=False)),
                ("last_id", models.CharField(blank=True, max_length=64)),
            ],
        ),
        _uuid_pk("eventpayeereview"),
        _uuid_pk("eventpayeerevision"),
        _uuid_pk("eventpayoutentry"),
        _uuid_pk("eventpayoutobligation"),
        _uuid_pk("payoutexportbatch"),
        _uuid_pk("payouthold"),
        _uuid_pk("receiptallocationoverride"),
        migrations.CreateModel(
            name="EventPayoutCommandReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation_id", models.UUIDField(unique=True)),
                ("command_digest", models.CharField(max_length=64)),
                ("response_reference", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
                ("obligation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="command_receipts", to="payments.eventpayoutobligation")),
            ],
        ),
        migrations.CreateModel(
            name="FinanceRetentionPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("receipt_days", models.PositiveIntegerField(default=2555)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="finance_retention_policy", to="makerspaces.makerspace")),
            ],
            options={
                "constraints": [models.CheckConstraint(condition=models.Q(("receipt_days__gte", 1), ("receipt_days__lte", 36500)), name="finance_receipt_retention_range")],
            },
        ),
        migrations.CreateModel(
            name="FinanceRetentionPolicyRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("policy_version", models.PositiveBigIntegerField()),
                ("receipt_days", models.PositiveIntegerField()),
                ("operation_id", models.UUIDField(unique=True)),
                ("command_digest", models.CharField(max_length=64)),
                ("reason_code", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="finance_policy_revisions", to="makerspaces.makerspace")),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("makerspace", "policy_version"), name="finance_policy_revision_unique")],
            },
        ),
        migrations.RunPython(backfill_cleanup_locators, migrations.RunPython.noop),
        migrations.RunSQL(GUARD_SQL, REVERSE_GUARD_SQL),
        migrations.RunSQL(ATTACHMENT_SCOPE_SQL, _previous_attachment_guard()),
        migrations.RunSQL(ATTACHMENT_FACTS_SQL, REVERSE_ATTACHMENT_FACTS_SQL),
    ]
