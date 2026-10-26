"""Audited superadmin PII windows (owner decisions #110e, #111 Q12). Additive only."""

import uuid

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0046_remove_external_checkin_user_id"),
        ("makerspaces", "0109_makerspace_security_lock"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformPiiAccessGrant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reason", models.CharField(max_length=300, validators=[django.core.validators.MinLengthValidator(10)])),
                ("opened_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField()),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("close_reason", models.CharField(
                    blank=True, choices=[("closed", "Closed"), ("expired", "Expired")], default="", max_length=16)),
                ("actor", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="+",
                    to="makerspaces.makerspace")),
                ("subject", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="+",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-opened_at",),
                "indexes": [models.Index(fields=["actor", "expires_at"], name="pii_grant_actor_expiry")],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("makerspace__isnull", False), ("subject__isnull", False), _connector="OR"),
                        name="pii_grant_has_scope"),
                    models.CheckConstraint(
                        condition=models.Q(("expires_at__gt", models.F("opened_at"))),
                        name="pii_grant_expires_after_open"),
                ],
            },
        ),
    ]
