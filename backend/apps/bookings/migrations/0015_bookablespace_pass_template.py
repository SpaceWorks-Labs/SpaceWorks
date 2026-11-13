from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0014_booking_arrival")]

    operations = [
        migrations.AddField(
            model_name="bookablespace", name="pass_template",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
