from django.db import migrations, models


CHOICES = [("members", "Members"), ("accounts", "Authenticated accounts"),
           ("invite", "Invited accounts"), ("participating_organizations", "Participating organizations")]


class Migration(migrations.Migration):
    dependencies = [("events", "0027_event_staff_tools")]
    operations = [
        *[migrations.AlterField(
            model_name=name, name="registration_audience",
            field=models.CharField(max_length=32, choices=CHOICES, default="members"),
        ) for name in ("event", "eventseries", "eventregistration")],
        *[migrations.AddField(
            model_name=name, name="organization_admission_blocked",
            field=models.BooleanField(default=False, editable=False),
        ) for name in ("event", "eventseries")],
    ]
