"""Booking arrival follows BK-B cancellation provenance."""
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_credentials(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    for pk in Booking.objects.using(schema_editor.connection.alias).values_list("pk", flat=True).iterator():
        Booking.objects.using(schema_editor.connection.alias).filter(pk=pk).update(checkin_token=uuid.uuid4())


IMMUTABLE_SQL = """
CREATE FUNCTION bookings_reject_checkin_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('app.allow_immutable_delete', true) = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'append-only/immutable booking arrival: % not allowed', TG_OP;
END;
$$;
CREATE TRIGGER bookings_checkin_immutable BEFORE UPDATE OR DELETE ON bookings_bookingcheckinevent
FOR EACH ROW EXECUTE FUNCTION bookings_reject_checkin_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0013_booking_cancellation_provenance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(model_name="booking", name="checkin_token",
                            field=models.UUIDField(null=True, editable=False)),
        migrations.RunPython(seed_credentials, migrations.RunPython.noop),
        migrations.AlterField(model_name="booking", name="checkin_token",
                              field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        migrations.AddField(model_name="booking", name="arrived_at",
                            field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.CreateModel(name="BookingCheckInEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("booking", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                         related_name="check_in_events", to="bookings.booking")),
            ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                       related_name="+", to=settings.AUTH_USER_MODEL)),
            ("action", models.CharField(max_length=8, choices=[("arrived", "Arrival confirmed"), ("reversed", "Arrival reversed")])),
            ("source", models.CharField(max_length=16, default="staff_qr", editable=False)),
            ("recorded_at", models.DateTimeField(auto_now_add=True)),
        ], options={"ordering": ["recorded_at", "pk"], "constraints": [models.CheckConstraint(
            condition=models.Q(action__in=("arrived", "reversed"), source="staff_qr"),
            name="booking_arrival_action_source")]}),
        migrations.RunSQL(IMMUTABLE_SQL,
            "DROP TRIGGER bookings_checkin_immutable ON bookings_bookingcheckinevent; DROP FUNCTION bookings_reject_checkin_mutation();"),
    ]
