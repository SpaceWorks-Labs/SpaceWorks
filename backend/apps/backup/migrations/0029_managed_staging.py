"""Private durable ciphertext lineage and issued presign drain inventory."""
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("backup", "0028_extension_digest_namespace")]
    operations = [
        migrations.CreateModel(name="ManagedStagedObject", fields=[
            ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ("owner", models.UUIDField(db_index=True, editable=False)),
            ("label", models.CharField(max_length=80, editable=False)),
            ("attempt", models.UUIDField(default=uuid.uuid4, editable=False)),
            ("identity", models.JSONField(editable=False)),
            ("object_key", models.CharField(max_length=512, unique=True, editable=False)),
            ("size", models.PositiveBigIntegerField(default=0)),
            ("sha256", models.CharField(max_length=64, blank=True)),
            ("available", models.BooleanField(default=False)),
            ("selected", models.BooleanField(default=False)),
            ("expires_at", models.DateTimeField(db_index=True)),
            ("delete_requested_at", models.DateTimeField(null=True)),
            ("deleted_at", models.DateTimeField(null=True)),
            ("retry_at", models.DateTimeField(null=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ], options={"indexes": [models.Index(fields=["owner", "label"], name="managed_stage_owner_label")], "constraints": [models.UniqueConstraint(fields=["owner", "label"], condition=models.Q(selected=True), name="managed_stage_selected_slot")]}),
        migrations.CreateModel(name="ManagedPresignLease", fields=[
            ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ("generation", models.PositiveBigIntegerField(editable=False)),
            ("expires_at", models.DateTimeField(db_index=True, editable=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ]),
        migrations.RunSQL("""
CREATE FUNCTION public.backup_managed_stage_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'staging receipts are permanent'; END IF;
 IF ROW(OLD.id,OLD.owner,OLD.label,OLD.attempt,OLD.identity,OLD.object_key,OLD.size,OLD.sha256,OLD.expires_at,OLD.created_at)
 IS DISTINCT FROM ROW(NEW.id,NEW.owner,NEW.label,NEW.attempt,NEW.identity,NEW.object_key,NEW.size,NEW.sha256,NEW.expires_at,NEW.created_at)
 OR (OLD.available AND NOT NEW.available) OR (OLD.selected AND NOT NEW.selected)
 OR (OLD.delete_requested_at IS NOT NULL AND NEW.delete_requested_at IS DISTINCT FROM OLD.delete_requested_at)
 THEN RAISE EXCEPTION 'staging lineage is immutable'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER backup_managed_stage_guard BEFORE UPDATE OR DELETE
ON public.backup_managedstagedobject FOR EACH ROW EXECUTE FUNCTION public.backup_managed_stage_guard();
""", "DROP TRIGGER backup_managed_stage_guard ON public.backup_managedstagedobject; DROP FUNCTION public.backup_managed_stage_guard();"),
    ]
