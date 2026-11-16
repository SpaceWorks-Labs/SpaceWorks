"""S-B: a staff device grant may follow any primary sign-in method (#62).

0041's ``device_grant_account_context`` still required ``login_method = 'password'`` for a
staff grant, while the 0049 trigger already accepts any primary method behind an enabled
factor. A person who signed in on the app with Google, Apple, GitHub or a phone code and then
asks for a staff grant (``auth/device/staff-grant``) therefore hit an IntegrityError. The
constraint now names the three primary methods; the trigger is unchanged.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0053_ip_access"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="devicegrant", name="device_grant_account_context"),
        migrations.AddConstraint(
            model_name="devicegrant",
            constraint=models.CheckConstraint(
                condition=(models.Q(status="revoked") | models.Q(
                    authority="member", staff_makerspace_id__isnull=True,
                ) | models.Q(authority="staff", staff_makerspace_id__isnull=False,
                             login_method__in=("password", "phone", "social"))),
                name="device_grant_account_context",
            ),
        ),
    ]
