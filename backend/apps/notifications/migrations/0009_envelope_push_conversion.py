"""CONVERT only after expansion, drained writers and M's history copy checkpoint."""
from django.db import migrations
from ._push_conversion_v1 import convert


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("notifications", "0008_envelope_push_expansion")]
    operations = [migrations.RunPython(convert)]
