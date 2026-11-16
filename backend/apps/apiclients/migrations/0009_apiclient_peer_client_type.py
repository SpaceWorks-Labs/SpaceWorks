from django.db import migrations, models


class Migration(migrations.Migration):
    """Release 2 (#193): the read-only peer client type for space-to-space public reads."""

    dependencies = [
        ("apiclients", "0008_import_approval_append_only"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apiclient",
            name="client_type",
            field=models.CharField(
                choices=[
                    ("browser", "Browser"),
                    ("server", "Server"),
                    ("peer", "Another space (public read-only)"),
                ],
                default="server",
                max_length=20,
            ),
        ),
    ]
