"""Merge node joining the mobile programme and integration branches (no operations)."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0039_analytics_m1f1"),
        ("accounts", "0037_governance_recovery_context"),
    ]

    operations = []
