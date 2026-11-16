"""Device Adapter API v1 (decisions 310-312): the `adapter` device kind and its device-bound state."""
import uuid

from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


def _user_fk(**extra):
    return models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="+",
                             to=settings.AUTH_USER_MODEL, **extra)


def _space_fk():
    return models.ForeignKey(on_delete=models.CASCADE, related_name="+", to="makerspaces.makerspace")


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0005_machine_integrations"),
        ("machines", "0030_service_notice_markers"),
        ("makerspaces", "__first__"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="device", name="kind",
            field=models.CharField(choices=[
                ("printer", "Printer"), ("label_printer", "Label printer"), ("generic", "Generic"),
                ("adapter", "Device adapter")], max_length=24)),
        migrations.CreateModel(
            name="AdapterProfile",
            fields=[
                ("device", models.OneToOneField(on_delete=models.CASCADE, primary_key=True, related_name="adapter_profile",
                                                serialize=False, to="devices.device")),
                ("makerspace", _space_fk()),
                ("protocol_version", models.PositiveSmallIntegerField(default=1)),
                ("adapter_kind", models.CharField(max_length=24)),
                ("vendor", models.CharField(blank=True, max_length=80)),
                ("software_version", models.CharField(blank=True, max_length=40)),
                ("capabilities", models.JSONField(default=list)),
                ("config_version", models.PositiveIntegerField(default=1)),
                ("hello_at", models.DateTimeField(default=timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name="AdapterBinding",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("target_type", models.CharField(choices=[
                    ("machine", "Machine"), ("machine_type", "Machine type"), ("storage_location", "Storage location"),
                    ("item", "Item"), ("box", "Box"), ("door", "Door"), ("space", "Space")], max_length=24)),
                ("target_id", models.CharField(blank=True, max_length=64)),
                ("external_ref", models.CharField(blank=True, max_length=120)),
                ("capabilities", models.JSONField(default=list)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("created_by", _user_fk()),
                ("device", models.ForeignKey(on_delete=models.CASCADE, related_name="adapter_bindings",
                                             to="devices.device")),
                ("machine", models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE,
                                              related_name="adapter_bindings", to="machines.machine")),
                ("makerspace", models.ForeignKey(on_delete=models.CASCADE, related_name="adapter_bindings",
                                                 to="makerspaces.makerspace")),
            ],
            options={
                "ordering": ("created_at", "id"),
                "indexes": [models.Index(fields=["device", "enabled"], name="adapter_binding_device_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("device", "target_type", "machine"),
                                            condition=Q(machine__isnull=False),
                                            name="devices_adapter_binding_machine_once"),
                    models.UniqueConstraint(fields=("device", "target_type", "target_id"), condition=~Q(target_id=""),
                                            name="devices_adapter_binding_target_once"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AdapterStatus",
            fields=[
                ("binding", models.OneToOneField(on_delete=models.CASCADE, primary_key=True, related_name="status",
                                                 serialize=False, to="devices.adapterbinding")),
                ("makerspace", _space_fk()),
                ("state", models.CharField(max_length=16)),
                ("payload", models.JSONField(default=dict)),
                ("observed_at", models.DateTimeField()),
                ("received_at", models.DateTimeField()),
            ],
        ),
        migrations.CreateModel(
            name="AdapterCommand",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("device_key_version", models.PositiveIntegerField()),
                ("capability", models.CharField(max_length=32)),
                ("command", models.CharField(max_length=32)),
                ("params", models.JSONField(default=dict)),
                ("status", models.CharField(choices=[
                    ("queued", "Queued"), ("leased", "Leased"), ("succeeded", "Succeeded"), ("failed", "Failed"),
                    ("expired", "Expired")], default="queued", max_length=12)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("lease_token_digest", models.CharField(blank=True, max_length=64, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
                ("result_code", models.CharField(blank=True, max_length=48)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("binding", models.ForeignKey(on_delete=models.CASCADE, related_name="commands",
                                              to="devices.adapterbinding")),
                ("created_by", _user_fk()),
                ("device", models.ForeignKey(on_delete=models.CASCADE, related_name="adapter_commands",
                                             to="devices.device")),
                ("makerspace", _space_fk()),
            ],
            options={
                "ordering": ("created_at", "id"),
                "indexes": [models.Index(fields=["device", "status", "created_at"],
                                         name="adapter_command_delivery_idx")],
                "constraints": [models.CheckConstraint(
                    condition=~Q(status="leased") | (Q(lease_token_digest__isnull=False)
                                                     & Q(lease_expires_at__isnull=False)),
                    name="adapter_command_lease_complete")],
            },
        ),
        migrations.CreateModel(
            name="AdapterEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("operation_id", models.UUIDField()),
                ("event_type", models.CharField(max_length=48)),
                ("capability", models.CharField(max_length=32)),
                ("data", models.JSONField(default=dict)),
                ("observed_at", models.DateTimeField()),
                ("received_at", models.DateTimeField(default=timezone.now)),
                ("binding", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="events",
                                              to="devices.adapterbinding")),
                ("device", models.ForeignKey(on_delete=models.CASCADE, related_name="adapter_events",
                                             to="devices.device")),
                ("makerspace", _space_fk()),
            ],
            options={
                "ordering": ("-received_at",),
                "indexes": [models.Index(fields=["device", "received_at"], name="adapter_event_device_idx")],
                "constraints": [models.UniqueConstraint(fields=("device", "operation_id"), name="adapter_event_once")],
            },
        ),
        migrations.CreateModel(
            name="AdapterCredential",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("nfc", "NFC"), ("pin", "PIN")], max_length=8)),
                ("digest", models.CharField(max_length=64)),
                ("label", models.CharField(blank=True, max_length=60)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("disabled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("created_by", _user_fk()),
                ("makerspace", _space_fk()),
                ("user", models.ForeignKey(on_delete=models.CASCADE, related_name="adapter_credentials",
                                           to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("makerspace", "kind", "digest"), name="adapter_credential_digest_once"),
                models.UniqueConstraint(fields=("makerspace", "user", "kind"), condition=Q(disabled_at__isnull=True),
                                        name="adapter_credential_one_live_per_kind"),
            ]},
        ),
        migrations.CreateModel(
            name="AdapterPose",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("target_type", models.CharField(max_length=24)),
                ("target_id", models.CharField(max_length=64)),
                ("pose", models.JSONField(default=dict)),
                ("note", models.CharField(blank=True, max_length=80)),
                ("updated_at", models.DateTimeField(default=timezone.now)),
                ("binding", models.ForeignKey(on_delete=models.CASCADE, related_name="poses",
                                              to="devices.adapterbinding")),
                ("makerspace", _space_fk()),
                ("saved_by", _user_fk()),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("binding", "target_type", "target_id"),
                                                             name="adapter_pose_once")]},
        ),
        migrations.CreateModel(
            name="AdapterAccessLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("credential_type", models.CharField(max_length=8)),
                ("allowed", models.BooleanField()),
                ("reason", models.CharField(max_length=48)),
                ("session_id_snapshot", models.PositiveBigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("binding", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="+",
                                              to="devices.adapterbinding")),
                ("device", models.ForeignKey(on_delete=models.CASCADE, related_name="adapter_access_logs",
                                             to="devices.device")),
                ("makerspace", _space_fk()),
                ("member", _user_fk()),
            ],
            options={"ordering": ("-created_at",),
                     "indexes": [models.Index(fields=["device", "created_at"], name="adapter_access_device_idx")]},
        ),
        migrations.CreateModel(
            name="AdapterUsageLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("operation_id", models.UUIDField()),
                ("session_id_snapshot", models.PositiveBigIntegerField(blank=True, null=True)),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField()),
                ("active_minutes", models.PositiveIntegerField(default=0)),
                ("idle_minutes", models.PositiveIntegerField(default=0)),
                ("outcome", models.CharField(max_length=12)),
                ("error_code", models.CharField(blank=True, max_length=48)),
                ("consumptions", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("binding", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="+",
                                              to="devices.adapterbinding")),
                ("device", models.ForeignKey(on_delete=models.CASCADE, related_name="adapter_usage_logs",
                                             to="devices.device")),
                ("makerspace", _space_fk()),
            ],
            options={"ordering": ("-created_at",),
                     "constraints": [models.UniqueConstraint(fields=("device", "operation_id"),
                                                             name="adapter_usage_once")]},
        ),
        migrations.CreateModel(
            name="AdapterWatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("active", "Active"), ("ended", "Ended")], default="active",
                                            max_length=8)),
                ("signals", models.JSONField(default=list)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("binding", models.ForeignKey(on_delete=models.CASCADE, related_name="watches",
                                              to="devices.adapterbinding")),
                ("makerspace", _space_fk()),
                ("viewer", _user_fk()),
            ],
        ),
    ]
