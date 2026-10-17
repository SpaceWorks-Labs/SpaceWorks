"""Join the three account-split lanes (sign-in, staff lifecycle, retention) built in parallel off 0034."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0035_as_p2_password_reset"),
        ("accounts", "0035_as_p3_invitation_snapshots"),
        ("accounts", "0035_as_p4_guarded_shell_restore"),
    ]
    operations = []
