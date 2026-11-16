import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0035_audience_organizations_and_staff_role_labels"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventSpeaker",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(max_length=200)),
                ("linked_via", models.CharField(blank=True, choices=[("staff_assigned", "Assigned by staff"), ("claimed", "Claimed by invite")], default="", max_length=16)),
                ("grants_check_in", models.BooleanField(default=False)),
                ("claim_token_digest", models.CharField(blank=True, default="", editable=False, max_length=64)),
                ("claim_expires_at", models.DateTimeField(blank=True, null=True)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("removed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="speakers", to="events.event")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
                ("removed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("section", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="speaker_identities", to="events.eventpagesection")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="event_speaking", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("created_at", "id"),
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(("removed_at__isnull", True), ("user__isnull", False)), fields=("event", "user"), name="event_speaker_active_account"),
                    models.UniqueConstraint(condition=models.Q(("claim_token_digest", ""), _negated=True), fields=("claim_token_digest",), name="event_speaker_claim_digest"),
                ],
            },
        ),
    ]
