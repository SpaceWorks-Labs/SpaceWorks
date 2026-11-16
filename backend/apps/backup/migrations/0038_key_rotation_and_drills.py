"""Platform key rotation state, restore drill reports and their settings (release 2 L11)."""
import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("backup", "0037_extracted_restore_points"),
        ("makerspaces", "__first__"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="platformbackupsettings", name="restore_drill_interval_days",
            field=models.PositiveSmallIntegerField(
                default=7, validators=[django.core.validators.MaxValueValidator(365)]),
        ),
        migrations.AddField(
            model_name="platformbackupsettings", name="archive_ready_notice_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="platformbackupsettings", name="reencrypt_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="BackupKeyFingerprint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("platform", "Platform key"),
                                                   ("server", "This server's restore key")], max_length=16)),
                ("fingerprint", models.CharField(max_length=64)),
                ("first_seen_at", models.DateTimeField(default=timezone.now)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                ("retired_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("kind", "-first_seen_at"),
                "constraints": [models.UniqueConstraint(fields=("kind", "fingerprint"),
                                                        name="backup_key_fingerprint_once")],
            },
        ),
        migrations.CreateModel(
            name="RestoreDrillReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("makerspace_id_snapshot", models.PositiveBigIntegerField()),
                ("archive_id_snapshot", models.UUIDField()),
                ("started_at", models.DateTimeField(default=timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("outcome", models.CharField(choices=[("passed", "Passed"), ("failed", "Failed")], max_length=16)),
                ("error_code", models.CharField(blank=True, max_length=48)),
                ("error_detail", models.CharField(blank=True, max_length=300)),
                ("checks", models.JSONField(blank=True, default=dict)),
                ("archive", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                              related_name="+", to="backup.backuparchive")),
                ("makerspace", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to="makerspaces.makerspace")),
            ],
            options={
                "ordering": ("-started_at",),
                "indexes": [models.Index(fields=["makerspace_id_snapshot", "started_at"],
                                         name="backup_drill_space_started")],
            },
        ),
    ]
