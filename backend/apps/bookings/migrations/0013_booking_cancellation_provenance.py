from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0012_booking_staff_grants")]

    operations = [
        migrations.AddField("booking", "cancelled_at", models.DateTimeField(null=True, blank=True)),
        migrations.AddField("booking", "status_before_cancel",
                            models.CharField(max_length=16, blank=True, default="")),
    ]
