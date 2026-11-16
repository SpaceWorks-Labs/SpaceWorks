"""Merge node joining the mobile programme and integration branches (no operations)."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0006_messaging_m1h"),
        ("notifications", "0004_notification_preferences"),
    ]

    operations = []
