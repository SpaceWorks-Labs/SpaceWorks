"""Device Adapter API media and data capabilities (decision 321): artifacts, telemetry history, config versions, offline
access cache, audio watch flags, diagnostics fields and offline access-log provenance."""
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _space_fk():
    return models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0008_adapter_push_type_profile"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField("adapterprofile", "firmware", models.CharField(blank=True, max_length=40)),
        migrations.AddField("adapterprofile", "health", models.CharField(blank=True, max_length=12)),
        migrations.AddField("adapterprofile", "health_at", models.DateTimeField(blank=True, null=True)),
        migrations.AddField("adapterwatch", "audio", models.BooleanField(default=False)),
        migrations.AddField("adapterwatch", "talk", models.BooleanField(default=False)),
        migrations.AddField("adapterwatch", "audio_notice_ack", models.BooleanField(default=False)),
        migrations.AddField("adapterwatch", "talk_presses", models.PositiveSmallIntegerField(default=0)),
        migrations.AddField("adapteraccesslog", "offline", models.BooleanField(default=False)),
        migrations.AddField("adapteraccesslog", "operation_id", models.UUIDField(blank=True, null=True)),
        migrations.AddConstraint("adapteraccesslog", models.UniqueConstraint(
            condition=models.Q(operation_id__isnull=False), fields=("device", "operation_id"),
            name="adapter_access_offline_once")),
        migrations.CreateModel(
            name="AdapterArtifact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("operation_id", models.UUIDField()),
                ("kind", models.CharField(max_length=20)),
                ("content_type", models.CharField(max_length=64)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("object_key", models.CharField(max_length=200)),
                ("status", models.CharField(choices=[("pending", "Pending upload"), ("ready", "Ready"),
                                                     ("purged", "Purged")], default="pending", max_length=8)),
                ("service_request_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("session_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("command_id", models.UUIDField(blank=True, null=True)),
                ("captured_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
                ("purged_at", models.DateTimeField(blank=True, null=True)),
                ("binding", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="artifacts",
                                              to="devices.adapterbinding")),
                ("makerspace", _space_fk()),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex("adapterartifact", models.Index(fields=["binding", "kind", "created_at"],
                                                            name="adapter_artifact_binding_idx")),
        migrations.AddIndex("adapterartifact", models.Index(fields=["status", "expires_at"],
                                                            name="adapter_artifact_expiry_idx")),
        migrations.AddConstraint("adapterartifact", models.UniqueConstraint(
            fields=("binding", "operation_id"), name="adapter_artifact_once")),
        migrations.CreateModel(
            name="AdapterTelemetryPoint",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("series", models.CharField(max_length=80)),
                ("resolution", models.PositiveSmallIntegerField(default=0)),
                ("ts", models.DateTimeField()),
                ("avg", models.FloatField()), ("min", models.FloatField()), ("max", models.FloatField()),
                ("n", models.PositiveIntegerField(default=1)),
                ("binding", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="telemetry",
                                              to="devices.adapterbinding")),
                ("makerspace", _space_fk()),
            ],
        ),
        migrations.AddIndex("adaptertelemetrypoint", models.Index(
            fields=["binding", "series", "resolution", "ts"], name="adapter_telemetry_read_idx")),
        migrations.AddIndex("adaptertelemetrypoint", models.Index(
            fields=["resolution", "ts"], name="adapter_telemetry_sweep_idx")),
        migrations.AddConstraint("adaptertelemetrypoint", models.UniqueConstraint(
            fields=("binding", "series", "resolution", "ts"), name="adapter_telemetry_point_once")),
        migrations.CreateModel(
            name="AdapterConfigVersion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.PositiveIntegerField()),
                ("config", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ack_outcome", models.CharField(blank=True, max_length=8)),
                ("ack_detail", models.CharField(blank=True, max_length=200)),
                ("acked_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name="adapter_config_versions", to="devices.device")),
                ("makerspace", _space_fk()),
            ],
            options={"ordering": ("-version",)},
        ),
        migrations.AddConstraint("adapterconfigversion", models.UniqueConstraint(
            fields=("device", "version"), name="adapter_config_version_once")),
        migrations.CreateModel(
            name="AdapterAccessCache",
            fields=[
                ("binding", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True,
                                                 related_name="access_cache", serialize=False,
                                                 to="devices.adapterbinding")),
                ("version", models.PositiveBigIntegerField(default=0)),
                ("entry_count", models.PositiveIntegerField(default=0)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("reconciled_at", models.DateTimeField(blank=True, null=True)),
                ("offline_decisions", models.PositiveIntegerField(default=0)),
                ("makerspace", _space_fk()),
            ],
        ),
    ]
