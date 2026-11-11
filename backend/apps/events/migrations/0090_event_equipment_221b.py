"""Decision 221b: per-event equipment return window and unlinkable workshop machine links."""
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0089_event_machine_booking_link"), ("bookings", "0026_booking_replaces")]
    operations = [
        migrations.AddField(
            model_name="event", name="equipment_return_hours",
            field=models.PositiveIntegerField(
                blank=True, null=True, validators=[django.core.validators.MaxValueValidator(720)]),
        ),
        migrations.AddField(
            model_name="eventmachinebookinglink", name="unlinked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="eventmachinebookinglink", name="booking",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="event_machine_links", to="bookings.booking"),
        ),
        migrations.AddConstraint(
            model_name="eventmachinebookinglink",
            constraint=models.UniqueConstraint(
                condition=models.Q(("booking__isnull", False), ("unlinked_at__isnull", True)),
                fields=("booking",), name="event_machine_link_live_booking_uniq"),
        ),
    ]
