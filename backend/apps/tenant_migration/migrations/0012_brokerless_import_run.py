from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tenant_migration", "0011_chunked_import_upload")]

    operations = [
        migrations.AddField(
            model_name="tenantimportjob",
            name="run_request",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="tenantimportjob",
            name="run_attempt",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
