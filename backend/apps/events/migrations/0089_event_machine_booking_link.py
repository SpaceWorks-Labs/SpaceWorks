from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("events", "0088_event_booking_decision_guard"),
                    ("bookings", "0026_booking_replaces"),
                    ("makerspaces", "0134_loan_context_generations")]
    operations = [migrations.CreateModel(name="EventMachineBookingLink", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="makerspaces.makerspace")),
        ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="machine_booking_links",
                                    to="events.event")),
        ("booking", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                         related_name="event_machine_link", to="bookings.booking")),
    ])]
