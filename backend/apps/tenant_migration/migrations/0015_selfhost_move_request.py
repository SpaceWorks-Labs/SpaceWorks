"""The Space Manager's self-host move request (release 2 L11, #128 C-23)."""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("tenant_migration", "0014_identity_decision_grant_staff_roles"),
        ("makerspaces", "__first__"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SelfHostMoveRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[
                    ("requested", "Requested"), ("approved", "Approved"), ("exporting", "Exporting"),
                    ("exported", "Exported"), ("rejected", "Rejected"), ("failed", "Export failed"),
                    ("cancelled", "Cancelled")], default="requested", max_length=16)),
                ("note", models.TextField(blank=True, max_length=2000)),
                ("requested_at", models.DateTimeField(default=timezone.now)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decision_note", models.CharField(blank=True, max_length=500)),
                ("recipient_fingerprint", models.CharField(blank=True, max_length=64)),
                ("artifact_path", models.CharField(blank=True, max_length=500)),
                ("artifact_sha256", models.CharField(blank=True, max_length=64)),
                ("exported_at", models.DateTimeField(blank=True, null=True)),
                ("failure_code", models.CharField(blank=True, max_length=48)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="selfhost_move_requests", to="makerspaces.makerspace")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                   related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-requested_at",),
                "constraints": [models.UniqueConstraint(
                    condition=Q(status__in=("requested", "approved", "exporting")), fields=("makerspace",),
                    name="tenant_migration_one_open_selfhost_move")],
            },
        ),
    ]
