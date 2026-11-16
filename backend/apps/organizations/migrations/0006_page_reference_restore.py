"""Restore global member references only through the exact backup inverse."""

from django.db import migrations
from apps.makerspaces.migrations._public_page_guards import sql
from apps.makerspaces.migrations._page_reference_restore import immutable_sql

ORIGINAL = sql("organizations", "organizationpublicpage")
FUNCTION = "organizations_organizationpublicpage_immutable"


class Migration(migrations.Migration):
    dependencies = [("organizations", "0005_public_pages")]
    operations = [migrations.RunSQL(
        immutable_sql(ORIGINAL, FUNCTION, restore=True),
        immutable_sql(ORIGINAL, FUNCTION, restore=False),
    )]
