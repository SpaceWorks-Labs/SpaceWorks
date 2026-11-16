from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0026_event_staff_grants")]

    operations = [
        migrations.AddField("event", "show_registration_count", models.BooleanField(default=True)),
        migrations.AddField("eventregistration", "cancelled_at", models.DateTimeField(null=True, blank=True)),
        migrations.AddField("eventregistration", "status_before_cancel", models.CharField(max_length=20, blank=True, default="")),
        migrations.AddField("eventregistration", "waitlist_position_at", models.DateTimeField(null=True, blank=True)),
    ]
