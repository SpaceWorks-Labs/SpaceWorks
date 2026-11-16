"""Paired space display screens (decision 307c)."""
import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("presence", "0003_presence_programme"),
        ("makerspaces", "0094_public_profile_contract"),
    ]

    operations = [
        migrations.CreateModel(
            name="DisplayScreen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_digest", models.CharField(editable=False, max_length=64, unique=True)),
                ("pairing_code", models.CharField(blank=True, default="", max_length=8)),
                ("code_expires_at", models.DateTimeField()),
                ("name", models.CharField(blank=True, default="", max_length=80)),
                ("panels", models.JSONField(blank=True, default=list)),
                ("rotation_seconds", models.PositiveSmallIntegerField(default=15)),
                ("announcement", models.CharField(blank=True, default="", max_length=280)),
                ("config_version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("makerspace", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="display_screens", to="makerspaces.makerspace")),
            ],
        ),
        migrations.AddConstraint(
            model_name="displayscreen",
            constraint=models.UniqueConstraint(condition=~Q(pairing_code=""), fields=("pairing_code",),
                                               name="display_screen_live_code_unique"),
        ),
        migrations.AddConstraint(
            model_name="displayscreen",
            constraint=models.CheckConstraint(
                condition=Q(rotation_seconds__gte=5) & Q(rotation_seconds__lte=120),
                name="display_screen_rotation_range"),
        ),
        migrations.AddIndex(
            model_name="displayscreen",
            index=models.Index(fields=["makerspace", "revoked_at"], name="display_space_revoked_idx"),
        ),
    ]
