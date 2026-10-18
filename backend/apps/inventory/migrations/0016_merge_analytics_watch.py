"""Merge node joining the mobile programme and integration branches (no operations)."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0015_analytics_m1f1"),
        ("inventory", "0015_watch_pending_index"),
    ]

    operations = []
