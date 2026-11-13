"""Platform locks on per-space security settings (owner decisions #110c, #111 Q9).

Additive only: a new table, no data. Existing spaces keep their stored settings and start
with no locks.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("makerspaces", "0108_membership_requires_member_accounts"),
    ]

    operations = [
        migrations.CreateModel(
            name="MakerspaceSecurityLock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=100)),
                ("floor", models.JSONField()),
                ("note", models.CharField(blank=True, default="", max_length=200)),
                ("locked_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("locked_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="+",
                    to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="security_locks",
                    to="makerspaces.makerspace")),
            ],
            options={
                "ordering": ("key",),
                "constraints": [models.UniqueConstraint(
                    fields=("makerspace", "key"), name="makerspace_security_lock_unique_key")],
            },
        ),
    ]
