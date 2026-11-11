from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("bookings", "0023_booking_phone_optional"),
                    ("hardware_requests", "0031_plain_admin_names"),
                    ("makerspaces", "0134_loan_context_generations")]
    operations = [migrations.CreateModel(name="BookingLoanContext", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("active", models.BooleanField(default=False)),
        ("revision", models.PositiveBigIntegerField(default=1)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("makerspace", models.ForeignKey(to="makerspaces.makerspace", on_delete=django.db.models.deletion.PROTECT)),
        ("request", models.OneToOneField(to="hardware_requests.hardwarerequest", on_delete=django.db.models.deletion.PROTECT)),
        ("booking", models.ForeignKey(to="bookings.booking", null=True, blank=True, on_delete=django.db.models.deletion.PROTECT)),
    ], options={"constraints": [
        models.CheckConstraint(condition=models.Q(models.Q(active=True, booking__isnull=False), models.Q(active=False, booking__isnull=True), _connector="OR"), name="booking_loan_context_active_ck"),
        models.CheckConstraint(condition=models.Q(revision__gte=1, revision__lte=9007199254740991), name="booking_loan_context_revision_ck"),
    ]})]
