"""Decision 358 B: a native passkey sign-in records ``login_method=passkey`` on its device grant.

A staff grant may follow any primary method (S-B, 0054), so the account-context constraint
admits ``passkey`` beside password, phone and social. No data changes; no trigger reads the value.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0061_channel_activity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="devicegrant",
            name="login_method",
            field=models.CharField(blank=True, default="", max_length=16, choices=[
                ("password", "Password"), ("phone", "Phone"), ("social", "Social"), ("passkey", "Passkey"),
            ]),
        ),
        migrations.RemoveConstraint(model_name="devicegrant", name="device_grant_account_context"),
        migrations.AddConstraint(
            model_name="devicegrant",
            constraint=models.CheckConstraint(
                condition=(models.Q(status="revoked")
                           | models.Q(authority="member", staff_makerspace_id__isnull=True, event_id__isnull=True)
                           | models.Q(authority="staff", staff_makerspace_id__isnull=False, event_id__isnull=True,
                                      login_method__in=("password", "phone", "social", "passkey"))
                           | models.Q(authority="event", staff_makerspace_id__isnull=True, event_id__isnull=False)),
                name="device_grant_account_context",
            ),
        ),
    ]
