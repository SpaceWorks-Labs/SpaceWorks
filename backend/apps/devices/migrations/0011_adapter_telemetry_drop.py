import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0010_adapter_job_external_id_binding"),
        ("makerspaces", "0131_makerspace_suspended_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdapterTelemetryDrop",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("day", models.DateField()),
                ("count", models.PositiveBigIntegerField(default=0)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
            ],
        ),
        migrations.AddConstraint(
            model_name="adaptertelemetrydrop",
            constraint=models.UniqueConstraint(fields=("makerspace", "day"), name="adapter_telemetry_drop_day"),
        ),
    ]
