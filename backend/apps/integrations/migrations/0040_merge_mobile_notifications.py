"""Merge node joining the mobile programme and integration branches (no operations)."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0035_messaging_tenant_tie"),
        ("integrations", "0039_bd_r2_notification_media"),
    ]

    operations = []
