"""Login security A+5: platform IP allow/deny rules and automatic blocks (schema only)."""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

IP_ACTIONS = ("allow", "deny")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0052_login_risk"),
    ]

    operations = [
        migrations.CreateModel(
            name="IPAccessRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cidr", models.CharField(max_length=49, unique=True)),
                ("action", models.CharField(choices=[(value, value) for value in IP_ACTIONS], max_length=8)),
                ("note", models.CharField(blank=True, default="", max_length=200)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("action__in", IP_ACTIONS)), name="ip_access_rule_action_known"),
                    models.CheckConstraint(condition=models.Q(("cidr", ""), _negated=True), name="ip_access_rule_cidr_present"),
                ],
            },
        ),
        migrations.CreateModel(
            name="IPAutoBlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ip_key", models.CharField(max_length=64, unique=True)),
                ("network", models.CharField(max_length=49)),
                ("blocked_until", models.DateTimeField()),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                "indexes": [models.Index(fields=["blocked_until"], name="ip_auto_block_until")],
            },
        ),
    ]
