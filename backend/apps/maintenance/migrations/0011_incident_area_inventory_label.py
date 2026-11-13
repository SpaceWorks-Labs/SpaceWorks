"""Decision 247/253(e): the stored choice label "Lending" becomes "Inventory" (label only, no data change)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maintenance", "0010_incident_involved_note_text")]

    operations = [
        migrations.AlterField(
            model_name="incident", name="area",
            field=models.CharField(
                choices=[("machines", "Machines"), ("lending", "Inventory"), ("events", "Events"),
                         ("bookings", "Rooms and bookings"), ("other", "Other (Space Manager only)")],
                default="other", max_length=10)),
    ]
