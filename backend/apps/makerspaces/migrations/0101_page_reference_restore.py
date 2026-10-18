"""Allow only backup-guarded inverses of projected nullable profile links."""

from django.db import migrations
from ._public_page_guards import sql
from ._page_reference_restore import immutable_sql

ORIGINAL = sql("makerspaces", "makerspacepublicpage")
FUNCTION = "makerspaces_makerspacepublicpage_immutable"


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0100_event_object_cleanup")]
    operations = [migrations.RunSQL(
        immutable_sql(ORIGINAL, FUNCTION, restore=True),
        immutable_sql(ORIGINAL, FUNCTION, restore=False),
    )]
