from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("events", "0086_consumable_plan_context"),
                    ("bookings", "0025_consumable_plan_context"),
                    ("makerspaces", "0134_loan_context_generations"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="EventBookingDecision", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("operation_id", models.UUIDField()),
        ("generation", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        ("revision", models.PositiveBigIntegerField(default=1)),
        ("billing_owner", models.CharField(default="booking", editable=False, max_length=12)),
        ("intent_version", models.PositiveSmallIntegerField(default=1, editable=False)),
        ("intent", models.JSONField(default=dict, editable=False)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="makerspaces.makerspace")),
        ("event", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to="events.event")),
        ("booking", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="bookings.booking")),
        ("creator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
    ], options={"constraints": [
        models.UniqueConstraint(fields=("makerspace", "operation_id"), name="event_booking_operation_uniq"),
        models.CheckConstraint(condition=models.Q(revision=1), name="event_booking_revision_ck"),
        models.CheckConstraint(condition=models.Q(billing_owner="booking"), name="event_booking_owner_ck"),
    ]})]
