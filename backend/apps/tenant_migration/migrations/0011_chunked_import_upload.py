from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tenant_migration", "0010_money_fingerprint")]

    operations = [
        migrations.AddField(
            model_name="tenantimportjob", name="upload_total_bytes",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenantimportjob", name="upload_received_bytes",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="tenantimportjob", name="status",
            field=models.CharField(
                choices=[
                    ("uploading", "Uploading"), ("pending", "Pending"),
                    ("awaiting_identity", "Awaiting identity decisions"),
                    ("ready", "Ready"), ("materializing", "Materializing"),
                    ("finalizing", "Finalizing"), ("completed", "Completed"),
                    ("failed", "Failed"), ("abandoned", "Abandoned"),
                ],
                default="pending", max_length=32,
            ),
        ),
    ]
