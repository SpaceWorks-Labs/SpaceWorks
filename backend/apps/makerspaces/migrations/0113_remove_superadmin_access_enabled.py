"""P1b (owner decision #110a): the superadmin is always on; drop the per-space switch.

backup/0010 and backup/0013 carry historical RunPython that reads this column, so
the drop must come after the backup app has passed them. The edge on backup/0030
(where archive custody went) orders it after both on a fresh install.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0112_public_closed_notice"),
        ("backup", "0030_remove_archive_custody"),
    ]

    operations = [
        migrations.RemoveField(model_name="makerspace", name="superadmin_access_enabled"),
    ]
