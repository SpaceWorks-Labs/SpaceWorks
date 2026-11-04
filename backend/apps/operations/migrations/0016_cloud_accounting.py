"""Durable physical usage, admission reservations and permanent bucket handoffs."""
import django.db.models.deletion
from importlib import import_module
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

HISTORY_GUARD = import_module("apps.operations.migrations.0015_storage_history_guards").FORWARD
HISTORY_GUARD = HISTORY_GUARD[:HISTORY_GUARD.index("CREATE TRIGGER")]
HISTORY_GUARD = HISTORY_GUARD.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1).replace(
    "(OLD.logical_role IS NOT NULL AND NEW.logical_role IS DISTINCT FROM OLD.logical_role)",
    """(OLD.logical_role IS NOT NULL AND NEW.logical_role IS DISTINCT FROM OLD.logical_role
        AND NOT (NEW.logical_role IS NULL AND EXISTS (
            SELECT 1 FROM public.operations_cloudstoragemigrationreceipt r
            WHERE r.role=OLD.logical_role AND r.source_identity=OLD.identity_fingerprint
            AND EXISTS (SELECT 1 FROM public.operations_storagecapabilitystate s
                        WHERE s.identity_fingerprint=r.destination_identity AND s.verified_at IS NOT NULL))))""")
OLD_HISTORY_GUARD = import_module("apps.operations.migrations.0015_storage_history_guards").FORWARD.split("CREATE TRIGGER")[0].replace(
    "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)


def preserve_capacity_receipts(apps, schema_editor):
    if (apps.get_model("operations", "CloudObjectReservation").objects.exists()
            or apps.get_model("operations", "CloudStorageMigrationReceipt").objects.exists()):
        raise IrreversibleError("Cannot discard upload capacity or permanent bucket handoff receipts.")


class Migration(migrations.Migration):
    dependencies = [("operations", "0015_storage_history_guards"), ("backup", "0028_extension_digest_namespace")]
    operations = [
        migrations.AlterField(model_name="cloudobjectusagereceipt", name="makerspace",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="makerspaces.makerspace")),
        migrations.CreateModel(name="CloudObjectAccount", fields=[
            ("identity", models.CharField(max_length=64, primary_key=True, serialize=False)),
            ("used", models.PositiveBigIntegerField(null=True)),
            ("sampled_at", models.DateTimeField(null=True)),
            ("started_at", models.DateTimeField(null=True)),
            ("cursor", models.JSONField(default=dict)),
            ("observed", models.PositiveBigIntegerField(default=0)),
            ("generation", models.PositiveBigIntegerField(default=0)),
            ("reason", models.CharField(default="storage_usage_unverified", max_length=100)),
        ]),
        migrations.CreateModel(name="CloudObjectReservation", fields=[
            ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
            ("bytes", models.PositiveBigIntegerField()), ("expires_at", models.DateTimeField()),
            ("state", models.CharField(default="reserved", max_length=16)),
            ("server_owned", models.BooleanField(default=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="operations.cloudobjectaccount")),
        ]),
        migrations.CreateModel(name="CloudStorageMigrationReceipt", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("role", models.CharField(max_length=128)), ("source_identity", models.CharField(max_length=64)),
            ("destination_identity", models.CharField(max_length=64)),
            ("inventory_digest", models.CharField(max_length=64)),
            ("source_contract", models.JSONField()),
            ("pause_owner", models.UUIDField()),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("retired_destination", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="backup.backupdestination")),
        ]),
        migrations.RunSQL("""
CREATE FUNCTION public.operations_cloud_receipt_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_TABLE_NAME='operations_cloudobjectusagereceipt' AND TG_OP='UPDATE'
    AND to_jsonb(NEW)->>'makerspace_id' IS NULL
    AND to_jsonb(NEW)-'makerspace_id'=to_jsonb(OLD)-'makerspace_id' THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'cloud accounting receipts are append-only';
END; $$;
CREATE TRIGGER operations_cloud_object_receipt_immutable BEFORE UPDATE OR DELETE
ON public.operations_cloudobjectusagereceipt FOR EACH ROW EXECUTE FUNCTION public.operations_cloud_receipt_immutable();
CREATE TRIGGER operations_storage_migration_immutable BEFORE UPDATE OR DELETE
ON public.operations_cloudstoragemigrationreceipt FOR EACH ROW EXECUTE FUNCTION public.operations_cloud_receipt_immutable();
CREATE FUNCTION public.operations_retired_storage_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
BEGIN
 IF EXISTS (SELECT 1 FROM public.operations_cloudstoragemigrationreceipt r WHERE r.retired_destination_id=OLD.id)
 AND (NEW.enabled OR NEW.endpoint_url IS DISTINCT FROM OLD.endpoint_url
      OR NEW.bucket IS DISTINCT FROM OLD.bucket OR NEW.region IS DISTINCT FROM OLD.region
      OR NEW.addressing_style IS DISTINCT FROM OLD.addressing_style) THEN
   RAISE EXCEPTION 'retired storage identity is retained for permanent late deletion';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER operations_retired_storage_guard BEFORE UPDATE ON public.backup_backupdestination
FOR EACH ROW EXECUTE FUNCTION public.operations_retired_storage_guard();
""", """
DROP TRIGGER IF EXISTS operations_retired_storage_guard ON public.backup_backupdestination;
DROP FUNCTION IF EXISTS public.operations_retired_storage_guard();
DROP TRIGGER IF EXISTS operations_storage_migration_immutable ON public.operations_cloudstoragemigrationreceipt;
DROP TRIGGER IF EXISTS operations_cloud_object_receipt_immutable ON public.operations_cloudobjectusagereceipt;
DROP FUNCTION IF EXISTS public.operations_cloud_receipt_immutable();
"""),
        migrations.RunSQL(HISTORY_GUARD, OLD_HISTORY_GUARD),
        migrations.RunPython(migrations.RunPython.noop, preserve_capacity_receipts),
    ]
