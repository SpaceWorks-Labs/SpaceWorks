import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Parity E-B2: the organiser badge role, a hand-set role lock, and append-only badge print receipts."""

    dependencies = [
        ("events", "0097_event_external_venue"),
        ("makerspaces", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="eventidcard", name="role",
            field=models.CharField(choices=[
                ("attendee", "Attendee"), ("speaker", "Speaker"), ("mentor", "Mentor"), ("judge", "Judge"),
                ("volunteer", "Volunteer"), ("crew", "Crew"), ("organiser", "Organiser")],
                default="attendee", max_length=10),
        ),
        migrations.AddField(model_name="eventidcard", name="role_locked",
                            field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name="EventBadgePrint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("method", models.CharField(choices=[
                    ("desk", "Desk"), ("station", "Station"), ("offline", "Offline desk"), ("bulk", "Bulk job")],
                    max_length=8)),
                ("stock", models.CharField(blank=True, default="", max_length=32)),
                ("role", models.CharField(blank=True, default="", max_length=12)),
                ("operation_id", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("printed_at", models.DateTimeField()),
                ("reported_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                            related_name="+", to=settings.AUTH_USER_MODEL)),
                ("card", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                           related_name="badge_prints", to="events.eventidcard")),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name="badge_prints", to="events.event")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
                ("registration", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                   related_name="badge_prints", to="events.eventregistration")),
            ],
            options={"ordering": ["event_id", "pk"]},
        ),
        migrations.AddConstraint(
            model_name="eventbadgeprint",
            constraint=models.UniqueConstraint(fields=("event", "operation_id"), name="event_badge_print_operation"),
        ),
        migrations.AddIndex(
            model_name="eventbadgeprint",
            index=models.Index(fields=["makerspace", "reported_at"], name="eventbadgeprint_space_month_idx"),
        ),
    ]
