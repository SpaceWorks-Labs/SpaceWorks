"""Drop the last Check-In leftover (owner decisions #79/#80).

The external Check-In API was retired in M7 and stays retired (#79). Nothing has
populated `User.external_checkin_user_id` since; #80 removes the field, its member
uniqueness constraint and every reader.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("accounts", "0042_deployment_app_identity")]

    operations = [
        migrations.RemoveConstraint(model_name="user", name="uniq_member_checkin_id"),
        migrations.RemoveField(model_name="user", name="external_checkin_user_id"),
    ]
