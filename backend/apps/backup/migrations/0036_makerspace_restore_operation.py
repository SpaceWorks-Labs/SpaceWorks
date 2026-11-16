"""Per-space restore journal (owner decisions #110d, #111 Q5/Q6/Q15/Q16, #113).

One row per restore of one makerspace, from preview to completion; at most one
unfinished restore per space.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("backup", "0035_space_backup_fields"),
        ("makerspaces", "0113_remove_superadmin_access_enabled"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MakerspaceRestoreOperation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source", models.CharField(
                    choices=[("space_archive", "One-space backup"), ("deployment_archive", "Whole-platform backup")],
                    default="space_archive", max_length=24)),
                ("stage", models.CharField(
                    choices=[("requested", "Requested"), ("staging", "Preparing preview"),
                             ("preview_ready", "Preview ready"), ("applying", "Restoring"),
                             ("completed", "Completed"), ("failed", "Failed"), ("aborted", "Cancelled")],
                    default="requested", max_length=16)),
                ("snapshot_at", models.DateTimeField(blank=True, null=True)),
                ("preview", models.JSONField(blank=True, default=dict)),
                ("preview_fingerprint", models.CharField(blank=True, max_length=64)),
                ("progress", models.JSONField(blank=True, default=dict)),
                ("report", models.JSONField(blank=True, default=dict)),
                ("error_code", models.CharField(blank=True, max_length=48)),
                ("error_detail", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("preview_ready_at", models.DateTimeField(blank=True, null=True)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("archive", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="space_restores", to="backup.backuparchive")),
                ("confirmed_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="space_restores",
                    to="makerspaces.makerspace")),
                ("requested_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL)),
                ("safety_archive", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to="backup.backuparchive")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="makerspacerestoreoperation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("stage__in", ("completed", "failed", "aborted")), _negated=True),
                fields=("makerspace",), name="backup_one_open_space_restore",
            ),
        ),
    ]
