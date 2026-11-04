"""Machine-integration foundations (release 2 L10, #76): type bindings and status snapshots."""
import uuid

from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0004_offline_event_choices"),
        ("machines", "0030_service_notice_markers"),
        ("makerspaces", "__first__"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MachineTypeIntegration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("printer_agent", "Printer agent")], max_length=24)),
                ("enabled", models.BooleanField(default=False)),
                ("config_schema_version", models.PositiveSmallIntegerField(default=1)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
                ("machine_type", models.ForeignKey(on_delete=models.CASCADE, related_name="integrations",
                                                   to="machines.machinetype")),
                ("makerspace", models.ForeignKey(on_delete=models.CASCADE, related_name="machine_type_integrations",
                                                 to="makerspaces.makerspace")),
            ],
            options={
                "ordering": ("created_at", "id"),
                "constraints": [
                    models.UniqueConstraint(fields=("makerspace", "machine_type", "kind"),
                                            name="devices_type_integration_once"),
                    models.CheckConstraint(condition=Q(config_schema_version__gte=1),
                                           name="devices_type_integration_schema_positive"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PrinterStatusSnapshot",
            fields=[
                ("device", models.OneToOneField(on_delete=models.CASCADE, primary_key=True,
                                                related_name="status_snapshot", serialize=False,
                                                to="devices.device")),
                ("schema_version", models.PositiveSmallIntegerField(default=1)),
                ("state", models.CharField(choices=[
                    ("idle", "Idle"), ("preparing", "Preparing"), ("printing", "Printing"), ("paused", "Paused"),
                    ("finished", "Finished"), ("failed", "Failed"), ("error", "Error")], max_length=16)),
                ("progress_percent", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("layer_current", models.PositiveIntegerField(blank=True, null=True)),
                ("layer_total", models.PositiveIntegerField(blank=True, null=True)),
                ("nozzle_temp_c", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True)),
                ("bed_temp_c", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True)),
                ("chamber_temp_c", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True)),
                ("spools", models.JSONField(blank=True, default=list)),
                ("clear_token", models.CharField(blank=True, max_length=64)),
                ("observed_at", models.DateTimeField()),
                ("received_at", models.DateTimeField()),
                ("makerspace", models.ForeignKey(on_delete=models.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(condition=Q(progress_percent__isnull=True) | Q(progress_percent__lte=100),
                                           name="devices_snapshot_progress_range"),
                ],
            },
        ),
    ]
