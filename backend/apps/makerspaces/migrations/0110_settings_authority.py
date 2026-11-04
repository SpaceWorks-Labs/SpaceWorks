"""Settings authority (owner decisions #101, #128 C-11): per-person grants and SM locks.

Additive only: two new tables. The grants that keep today's editors able to edit are
created by the data migration that follows (0111), audited as `via=migration`.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _user(**extra):
    return models.ForeignKey(
        null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
        to=settings.AUTH_USER_MODEL, **extra,
    )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("makerspaces", "0109_makerspace_security_lock"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModuleSettingsGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module", models.CharField(max_length=32)),
                ("granted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("granted_by", _user(blank=True)),
                ("grantee", _user()),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="settings_grants",
                    to="makerspaces.makerspace")),
                ("revoked_by", _user(blank=True)),
            ],
            options={
                "ordering": ("module", "granted_at", "id"),
                "indexes": [models.Index(fields=["makerspace", "module"], name="settings_grant_space_module_idx")],
                "constraints": [models.UniqueConstraint(
                    condition=models.Q(("revoked_at__isnull", True)),
                    fields=("makerspace", "module", "grantee"), name="settings_grant_one_live_per_person")],
            },
        ),
        migrations.CreateModel(
            name="ModuleSettingLock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("setting_key", models.CharField(max_length=100)),
                ("note", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("locked_by", _user(blank=True)),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="setting_locks",
                    to="makerspaces.makerspace")),
                ("released_by", _user(blank=True)),
            ],
            options={
                "ordering": ("setting_key", "created_at", "id"),
                "constraints": [models.UniqueConstraint(
                    condition=models.Q(("released_at__isnull", True)),
                    fields=("makerspace", "setting_key"), name="setting_lock_one_live_per_key")],
            },
        ),
    ]
