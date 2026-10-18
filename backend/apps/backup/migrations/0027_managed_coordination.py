"""Additive cloud coordination. No host deployment is adopted or enabled."""
import uuid
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [("backup", "0026_backfill_backup_module")]
    operations = [
        migrations.CreateModel(name='ManagedDeploymentState', fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deployment_id', models.UUIDField(editable=False, unique=True)),
                ('database_uuid', models.UUIDField(editable=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ], options={'constraints': [models.CheckConstraint(condition=models.Q(pk=1), name="managed_deployment_singleton")]}),
        migrations.CreateModel(name='ManagedCaptureState', fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('generation', models.PositiveBigIntegerField(default=1)),
                ('paused_by', models.UUIDField(null=True, editable=False)),
                ('paused_at', models.DateTimeField(null=True, editable=False)),
                ('drain_until', models.DateTimeField(null=True, editable=False)),
            ], options={'constraints': [
            models.CheckConstraint(condition=models.Q(pk=1), name="managed_capture_singleton"),
            models.CheckConstraint(condition=models.Q(generation__gte=1), name="managed_capture_generation_positive"),
            models.CheckConstraint(
                condition=(models.Q(paused_by__isnull=True, paused_at__isnull=True, drain_until__isnull=True)
                           | models.Q(paused_by__isnull=False, paused_at__isnull=False, drain_until__isnull=False)),
                name="managed_capture_pause_complete",
            ),
        ]}),
        migrations.CreateModel(name='ManagedWriterBoundary', fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('generation', models.PositiveBigIntegerField(editable=False, db_index=True)),
                ('category', models.CharField(max_length=24, editable=False)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(null=True, editable=False)),
                ('uncertain', models.BooleanField(default=False)),
            ], options={'indexes': [models.Index(fields=["finished_at", "generation"], name="managed_writer_active")]}),
        migrations.RunSQL("\nCREATE OR REPLACE FUNCTION public.backup_managed_binding_immutable()\nRETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$\nBEGIN\n  RAISE EXCEPTION 'managed deployment binding is immutable';\nEND;\n$$;\nCREATE TRIGGER backup_managed_binding_no_mutation\nBEFORE UPDATE OR DELETE ON public.backup_manageddeploymentstate\nFOR EACH ROW EXECUTE FUNCTION public.backup_managed_binding_immutable();\n", 'DROP TRIGGER IF EXISTS backup_managed_binding_no_mutation ON public.backup_manageddeploymentstate; DROP FUNCTION IF EXISTS public.backup_managed_binding_immutable();'),
    ]
