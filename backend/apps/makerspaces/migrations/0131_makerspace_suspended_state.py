# Owner decision #185: a superadmin can pause (suspend) a space. Choices only: no data change.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0130_charges_donations_default_on")]

    operations = [
        migrations.AlterField(
            model_name="makerspace",
            name="lifecycle_state",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("importing", "Importing"),
                    ("aborted", "Aborted"),
                    ("suspended", "Suspended"),
                ],
                db_index=True,
                default="active",
                max_length=16,
            ),
        ),
    ]
