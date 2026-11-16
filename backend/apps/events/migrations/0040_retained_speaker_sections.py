"""Draft removal must not sever durable account-linked speaker credit."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0039_website_snapshot_guards")]
    operations = [migrations.AddField(
        model_name="eventpagesection", name="is_working", field=models.BooleanField(default=True),
    )]
