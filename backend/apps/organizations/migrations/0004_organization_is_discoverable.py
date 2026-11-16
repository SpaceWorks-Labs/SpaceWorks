from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("organizations", "0003_organization_presentation_and_governance")]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="is_discoverable",
            field=models.BooleanField(default=False),
        ),
    ]
