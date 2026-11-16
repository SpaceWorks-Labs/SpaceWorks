"""Pin the reconciled module field after the branch choice-state union.

Module keys (including presence, SMS and WhatsApp) are validated as a JSON list
by the module registry. Scalar Django choices would reject valid lists.
"""
import apps.makerspaces.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0097_reconcile_enabled_modules")]
    operations = [migrations.AlterField(
        model_name="makerspace", name="enabled_modules",
        field=models.JSONField(blank=True, default=apps.makerspaces.models.default_enabled_modules),
    )]
