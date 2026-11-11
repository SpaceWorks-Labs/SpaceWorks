from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("events", "0084_certificate_holder_name"),
                    ("hardware_requests", "0031_plain_admin_names"),
                    ("makerspaces", "0134_loan_context_generations")]
    operations = [migrations.CreateModel(name="EventLoanContext", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("active", models.BooleanField(default=False)),
        ("revision", models.PositiveBigIntegerField(default=1)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("makerspace", models.ForeignKey(to="makerspaces.makerspace", on_delete=django.db.models.deletion.PROTECT)),
        ("request", models.OneToOneField(to="hardware_requests.hardwarerequest", on_delete=django.db.models.deletion.PROTECT)),
        ("event", models.ForeignKey(to="events.event", null=True, blank=True, on_delete=django.db.models.deletion.PROTECT)),
        ("participant_registration", models.ForeignKey(to="events.eventregistration", null=True, blank=True, on_delete=django.db.models.deletion.PROTECT)),
    ], options={"constraints": [
        models.CheckConstraint(condition=models.Q(models.Q(active=True, event__isnull=False), models.Q(active=False, event__isnull=True, participant_registration__isnull=True), _connector="OR"), name="event_loan_context_active_ck"),
        models.CheckConstraint(condition=models.Q(revision__gte=1, revision__lte=9007199254740991), name="event_loan_context_revision_ck"),
    ]})]
