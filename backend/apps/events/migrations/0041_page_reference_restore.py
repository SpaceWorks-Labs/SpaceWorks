"""Keep event history immutable while permitting guarded slice inverses."""

from importlib import import_module
from django.db import migrations
from apps.makerspaces.migrations._page_reference_restore import immutable_sql

ORIGINAL = import_module("apps.events.migrations.0039_website_snapshot_guards").SQL
FUNCTION = "event_snapshot_immutable"


class Migration(migrations.Migration):
    dependencies = [("events", "0040_retained_speaker_sections")]
    operations = [migrations.RunSQL(
        immutable_sql(ORIGINAL, FUNCTION, restore=True),
        immutable_sql(ORIGINAL, FUNCTION, restore=False),
    )]
