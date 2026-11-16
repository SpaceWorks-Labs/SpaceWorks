"""Device Adapter API v1, part 4: webhook push endpoints, their delivery log, and per-machine-type safety profiles."""
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _user_fk():
    return models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                             to=settings.AUTH_USER_MODEL)


def _space_fk():
    return models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                             to="makerspaces.makerspace")


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0007_adapter_jobs_kiosk_media"),
        ("machines", "0030_service_notice_markers"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdapterWebhook",
            fields=[
                ("device", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True,
                                                related_name="adapter_webhook", serialize=False, to="devices.device")),
                ("url", models.CharField(max_length=500)),
                ("enabled", models.BooleanField(default=True)),
                ("secret_version", models.PositiveIntegerField(default=1)),
                ("include_data", models.BooleanField(default=False)),
                ("consecutive_failures", models.PositiveSmallIntegerField(default=0)),
                ("disabled_at", models.DateTimeField(blank=True, null=True)),
                ("disabled_reason", models.CharField(blank=True, max_length=48)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_by", _user_fk()),
                ("makerspace", _space_fk()),
            ],
        ),
        migrations.CreateModel(
            name="AdapterWebhookDelivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(max_length=48)),
                ("envelope", models.JSONField(default=dict)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("delivered", "Delivered"),
                                                     ("dead", "Gave up")], default="pending", max_length=12)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_status_code", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, max_length=48)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name="adapter_webhook_deliveries", to="devices.device")),
                ("makerspace", _space_fk()),
            ],
            options={"ordering": ("-created_at",),
                     "indexes": [models.Index(fields=["status", "next_attempt_at"], name="adapter_push_due_idx")]},
        ),
        migrations.CreateModel(
            name="AdapterTypeProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("machine_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                   to="machines.machinetype")),
                ("makerspace", _space_fk()),
                ("updated_by", _user_fk()),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("makerspace", "machine_type"),
                                                             name="adapter_type_profile_once")]},
        ),
    ]
