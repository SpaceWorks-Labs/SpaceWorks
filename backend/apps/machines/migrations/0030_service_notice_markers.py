from django.db import migrations, models
from django.db.models import F


def mark_historical_milestones(apps, schema_editor):
    """Existing lifecycle mail already went out: never replay it as a new milestone.

    Sends nothing. Markers mean "intent reserved"; a historical start/completion is
    treated as already reserved so the durable requester notices begin with new events.
    """
    Request = apps.get_model("machines", "MachineServiceRequest")
    Request.objects.filter(started_at__isnull=False, started_notice_at__isnull=True).update(
        started_notice_at=F("started_at"))
    Request.objects.filter(completed_at__isnull=False, completed_notice_at__isnull=True).update(
        completed_notice_at=F("completed_at"))


class Migration(migrations.Migration):
    dependencies = [
        ("machines", "0029_analytics_m1f1"),
    ]

    operations = [
        migrations.AlterField(
            model_name="machineservicerequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"), ("accepted", "Accepted"), ("in_progress", "In progress"),
                    ("completed", "Completed"), ("collected", "Collected"), ("rejected", "Rejected"),
                    ("failed", "Failed"), ("cancelled", "Cancelled"),
                ],
                db_index=True, default="pending", max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="machineservicerequest",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="machineservicerequest",
            name="started_notice_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="machineservicerequest",
            name="completed_notice_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="machineservicerequest",
            name="cancelled_notice_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="machineservicerequest",
            name="imported_head_notified",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.RunPython(mark_historical_milestones, migrations.RunPython.noop),
    ]
