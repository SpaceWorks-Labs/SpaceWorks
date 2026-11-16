import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0011_adapter_telemetry_drop"),
        ("makerspaces", "0131_makerspace_suspended_state"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ShelfCheck",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("scope_label", models.CharField(blank=True, max_length=80)),
                ("entries", models.JSONField(default=list)),
                ("ok_count", models.PositiveIntegerField(default=0)),
                ("attention_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("checked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
            ],
            options={"indexes": [models.Index(fields=["makerspace", "-created_at"],
                                              name="shelf_check_ms_created_idx")]},
        ),
    ]
