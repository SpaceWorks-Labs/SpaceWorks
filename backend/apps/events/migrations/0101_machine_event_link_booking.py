import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Decision 342 (gap closed): a machine-time booking can carry the event link too."""

    dependencies = [
        ("events", "0100_machine_event_links"),
        ("bookings", "0031_organization_hours_bank"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="machineeventlink", name="machine_event_link_one_subject"),
        migrations.AddField(
            model_name="machineeventlink",
            name="booking",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                       related_name="event_link", to="bookings.booking"),
        ),
        migrations.AddConstraint(
            model_name="machineeventlink",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("booking__isnull", True), ("service_request__isnull", True), ("session__isnull", False)),
                    models.Q(("booking__isnull", True), ("service_request__isnull", False), ("session__isnull", True)),
                    models.Q(("booking__isnull", False), ("service_request__isnull", True), ("session__isnull", True)),
                    _connector="OR"),
                name="machine_event_link_one_subject"),
        ),
    ]
