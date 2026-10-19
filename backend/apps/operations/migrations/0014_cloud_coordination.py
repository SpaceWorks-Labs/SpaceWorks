"""Additive cloud coordination. No host deployment is adopted or enabled."""
import uuid
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [("operations", "0013_stocktake_discipline"), ("integrations", "0040_email_providers")]
    operations = [
        migrations.CreateModel(name='CloudTaskState', fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100, unique=True)),
                ('token', models.UUIDField(null=True, default=None)),
                ('generation', models.PositiveBigIntegerField(default=0)),
                ('status', models.CharField(max_length=16, default="idle", choices=[('idle', 'idle'), ('running', 'running'), ('completed', 'completed'), ('deferred', 'deferred'), ('failed', 'failed'), ('uncertain', 'uncertain'), ('disabled', 'disabled')])),
                ('checkpoint', models.JSONField(default=dict)),
                ('last_attempt_at', models.DateTimeField(null=True)),
                ('heartbeat_at', models.DateTimeField(null=True)),
                ('last_completed_at', models.DateTimeField(null=True)),
                ('next_due_at', models.DateTimeField(null=True, db_index=True)),
                ('failure_code', models.CharField(max_length=64, blank=True, default="")),
            ], options={'constraints': [
            models.CheckConstraint(condition=models.Q(status__in=[
                "idle", "running", "completed", "deferred", "failed", "uncertain", "disabled",
            ]), name="cloud_task_status_valid"),
            models.CheckConstraint(condition=(~models.Q(status__in=["running", "uncertain"]) |
                models.Q(token__isnull=False, last_attempt_at__isnull=False, heartbeat_at__isnull=False)),
                name="cloud_task_claim_complete"),
            models.CheckConstraint(condition=models.Q(generation__gte=0), name="cloud_task_generation_valid"),
        ], 'indexes': [models.Index(fields=["status", "next_due_at"], name="cloud_task_due")]}),
        migrations.CreateModel(name='CloudTickRun', fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('started_at', models.DateTimeField(default=timezone.now, db_index=True)),
                ('finished_at', models.DateTimeField(null=True, db_index=True)),
                ('duration_ms', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(max_length=16, default="running", choices=[('running', 'running'), ('completed', 'completed'), ('failed', 'failed')])),
                ('completed', models.PositiveIntegerField(default=0)),
                ('deferred', models.PositiveIntegerField(default=0)),
                ('failed', models.PositiveIntegerField(default=0)),
            ], options={'constraints': [
            models.CheckConstraint(condition=models.Q(status__in=["running", "completed", "failed"]),
                                   name="cloud_tick_status_valid"),
            models.CheckConstraint(condition=(models.Q(status="running", finished_at__isnull=True) |
                models.Q(status__in=["completed", "failed"], finished_at__isnull=False)),
                name="cloud_tick_finish_complete"),
            models.CheckConstraint(condition=(models.Q(finished_at__isnull=True) |
                models.Q(finished_at__gte=models.F("started_at"))), name="cloud_tick_time_order"),
        ], 'indexes': [models.Index(fields=["status", "started_at"], name="cloud_tick_status_start")]}),
        migrations.CreateModel(name='CloudTickRateWindow', fields=[
                ('key', models.CharField(max_length=32, primary_key=True, serialize=False)),
                ('window', models.DateTimeField()),
                ('hits', models.PositiveIntegerField(default=0)),
            ], options={'constraints': [
            models.CheckConstraint(condition=models.Q(key__in=["ingress", "authenticated"]),
                                   name="cloud_tick_rate_key_valid"),
            models.CheckConstraint(condition=models.Q(hits__gte=0), name="cloud_tick_rate_hits_valid"),
        ]}),
        migrations.CreateModel(name='CloudEmailBudgetAccount', fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=80, unique=True)),
                ('provider', models.CharField(max_length=16)),
                ('reset_timezone', models.CharField(max_length=64)),
            ], options={}),
        migrations.CreateModel(name='CloudEmailReservation', fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account', models.ForeignKey("operations.CloudEmailBudgetAccount", on_delete=models.PROTECT)),
                ('log', models.ForeignKey("integrations.EmailLog", null=True, on_delete=models.SET_NULL)),
                ('attempt_key', models.CharField(max_length=200, unique=True)),
                ('provider', models.CharField(max_length=16)),
                ('day', models.DateField()),
                ('month', models.DateField()),
                ('accepted_day', models.DateField(null=True)),
                ('accepted_month', models.DateField(null=True)),
                ('recipients', models.PositiveIntegerField()),
                ('state', models.CharField(max_length=12, choices=[(v, v) for v in (
        "reserved", "accepted", "uncertain", "released",
    )])),
                ('provider_message_id', models.CharField(max_length=200, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ], options={'constraints': [
            models.CheckConstraint(condition=models.Q(recipients__gte=1), name="cloud_email_recipients_positive"),
            models.CheckConstraint(condition=models.Q(state__in=["reserved", "accepted", "uncertain", "released"]),
                                   name="cloud_email_state_valid"),
        ], 'indexes': [
            models.Index(fields=["account", "state", "day"], name="cloud_email_account_day"),
            models.Index(fields=["account", "state", "month"], name="cloud_email_account_month"),
        ]}),
        migrations.CreateModel(name='StorageCapabilityState', fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identity_fingerprint', models.CharField(max_length=64, unique=True)),
                ('identity', models.JSONField()),
                ('logical_role', models.CharField(max_length=128, null=True, unique=True)),
                ('generation', models.PositiveIntegerField(default=1)),
                ('configuration_fingerprint', models.CharField(max_length=64)),
                ('history_possible', models.BooleanField(default=False)),
                ('facts', models.JSONField(default=dict)),
                ('verified_at', models.DateTimeField(null=True, blank=True)),
            ], options={'constraints': [models.CheckConstraint(
            condition=models.Q(generation__gte=1, generation__lte=2147483647),
            name="storage_capability_generation_valid",
        )]}),
        migrations.CreateModel(name='CloudUsageSample', fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('metric', models.CharField(max_length=16, choices=[(v, v) for v in ("database", "objects", "email")])),
                ('makerspace', models.ForeignKey("makerspaces.Makerspace", null=True, on_delete=models.CASCADE)),
                ('scope', models.CharField(max_length=16, choices=[(v, v) for v in ("deployment", "tenant", "provider_account")])),
                ('used', models.PositiveBigIntegerField(null=True)),
                ('uncertain', models.PositiveBigIntegerField(default=0)),
                ('sampled_at', models.DateTimeField()),
                ('source', models.CharField(max_length=100)),
                ('reason_code', models.CharField(max_length=100, blank=True)),
                ('checkpoint', models.JSONField(default=dict)),
                ('configured_cap', models.PositiveBigIntegerField(null=True)),
                ('cap_source', models.CharField(max_length=200, blank=True)),
                ('cap_verified_on', models.DateField(null=True)),
            ], options={'indexes': [models.Index(fields=["metric", "scope", "makerspace", "-sampled_at"], name="cloud_usage_latest")]}),
        migrations.CreateModel(name='CloudObjectUsageReceipt', fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('operation_key', models.CharField(max_length=128, unique=True)),
                ('makerspace', models.ForeignKey("makerspaces.Makerspace", null=True, on_delete=models.CASCADE)),
                ('bucket_alias', models.CharField(max_length=100)),
                ('object_key_digest', models.CharField(max_length=64)),
                ('generation', models.CharField(max_length=100)),
                ('bytes', models.PositiveBigIntegerField()),
                ('operation', models.CharField(max_length=16, choices=[("finalize", "finalize"), ("delete_confirmed", "delete_confirmed")])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ], options={}),
    ]
