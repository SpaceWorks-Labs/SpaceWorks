"""Login security A+4: remembered devices, familiar networks and security alerts (schema only)."""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

GRANULARITIES = ("ipv4_24", "ipv6_64")
ALERT_KINDS = ("new_device", "password_changed", "mfa_changed", "lockout")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0051_webauthn"),
    ]

    operations = [
        migrations.CreateModel(
            name="KnownDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_hmac", models.CharField(max_length=64)),
                ("ua_label", models.CharField(blank=True, default="", max_length=120)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_verified_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="known_devices", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("user", "device_hmac"), name="known_device_unique_per_user")],
            },
        ),
        migrations.CreateModel(
            name="KnownNetwork",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("granularity", models.CharField(choices=[(value, value) for value in GRANULARITIES], max_length=16)),
                ("prefix_hmac", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_seen", models.DateTimeField()),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="known_networks", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["last_seen"], name="known_network_last_seen")],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "granularity", "prefix_hmac"), name="known_network_unique_per_user"),
                    models.CheckConstraint(condition=models.Q(("granularity__in", GRANULARITIES)), name="known_network_granularity_known"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SecurityAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[(value, value) for value in ALERT_KINDS], max_length=24)),
                ("nonce_digest", models.CharField(max_length=64, unique=True)),
                ("network_label", models.CharField(blank=True, max_length=120, null=True)),
                ("ua_label", models.CharField(blank=True, max_length=120, null=True)),
                ("sent_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="security_alerts", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["expires_at"], name="security_alert_expiry")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("kind__in", ALERT_KINDS)), name="security_alert_kind_known"),
                    models.CheckConstraint(condition=models.Q(("expires_at__gt", models.F("sent_at"))), name="security_alert_expires_after_sending"),
                ],
            },
        ),
    ]
