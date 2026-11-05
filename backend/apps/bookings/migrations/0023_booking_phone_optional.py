from django.db import migrations, models


class Migration(migrations.Migration):
    """A booking's phone is optional: the booking form asks for none and a member may have none."""

    dependencies = [
        ("bookings", "0022_l12_machine_time_booking"),
    ]

    operations = [
        migrations.AlterField(
            model_name="booking",
            name="phone",
            field=models.TextField(blank=True),
        ),
    ]
