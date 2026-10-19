import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    """State-only: 0038 declared these UUID primary keys without serialize=False."""

    dependencies = [
        ("accounts", "0038_events_programme_schema"),
    ]

    operations = [
        migrations.AlterField(
            model_name="membersaveddetail",
            name="id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="saveddetailcommandreceipt",
            name="id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="saveddetailsobjectcleanup",
            name="id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="saveddetailupdateintent",
            name="id",
            field=models.UUIDField(editable=False, primary_key=True, serialize=False),
        ),
    ]
