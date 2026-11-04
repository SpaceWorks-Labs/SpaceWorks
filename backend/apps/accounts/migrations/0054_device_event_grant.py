"""#173 (lane L21b): native event-role grants, a step-up limited to one event's programme routes."""

from django.db import migrations, models

from ._0054_event_device_guard import AFTER, BEFORE


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0053_ip_access"),
    ]

    operations = [
        migrations.AddField(
            model_name="devicegrant",
            name="event_id",
            field=models.PositiveBigIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="devicegrant",
            name="authority",
            field=models.CharField(choices=[("member", "Member"), ("staff", "Staff"), ("event", "Event role")],
                                   default="member", max_length=16),
        ),
        migrations.RemoveConstraint(model_name="devicegrant", name="device_grant_account_context"),
        migrations.AddConstraint(
            model_name="devicegrant",
            constraint=models.CheckConstraint(
                condition=(models.Q(status="revoked")
                           | models.Q(authority="member", staff_makerspace_id__isnull=True, event_id__isnull=True)
                           | models.Q(authority="staff", staff_makerspace_id__isnull=False, event_id__isnull=True,
                                      login_method="password")
                           | models.Q(authority="event", staff_makerspace_id__isnull=True, event_id__isnull=False)),
                name="device_grant_account_context",
            ),
        ),
        migrations.RunSQL(AFTER, BEFORE),
    ]
