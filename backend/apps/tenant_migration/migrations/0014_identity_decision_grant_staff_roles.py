from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenant_migration", "0013_tenant_dump_without_custody"),
    ]

    operations = [
        migrations.AddField(
            model_name="importidentitydecision",
            name="grant_staff_roles",
            field=models.BooleanField(default=False),
        ),
    ]
