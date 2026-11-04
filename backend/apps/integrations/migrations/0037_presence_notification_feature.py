"""Expose the existing personal presence feature in the matrix; choices only."""

from django.db import migrations, models


FEATURE_CHOICES = [
    ("hardware_requests", "Hardware requests"),
    ("printing", "Printing"),
    ("events", "Events"),
    ("bookings", "Bookings"),
    ("maintenance", "Maintenance"),
    ("members", "Members"),
    ("api_access", "API access"),
    ("devices", "Devices"),
    ("payments", "Payments"),
    ("stock", "Stock and procurement"),
    ("certifications", "Certifications"),
    ("presence", "Presence"),
]


class Migration(migrations.Migration):
    dependencies = [("integrations", "0036_notification_pii_fences")]

    operations = [
        migrations.AlterField(
            model_name=model_name,
            name="feature",
            field=models.CharField(choices=FEATURE_CHOICES, max_length=32),
        )
        for model_name in (
            "chattemplate", "notificationdeliverylog", "notificationpreference",
            "notificationrecipient",
        )
    ]
